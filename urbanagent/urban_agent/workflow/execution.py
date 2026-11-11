# -*- coding: utf-8 -*-
"""Stage 3 — Execution module: f_exec : (G, T_MCP, E_t) -> O.

Traverses the dependency graph in topological order.  For each node v_i the
LLM policy pi performs schema-constrained instantiation (Eq. 2):

    (tau_k, p_i) = pi(v_i, O_<i, C_hard | Schema(T))

implemented with native function calling restricted to the node's candidate
tools, so parameter generation is compelled to comply with each tool's JSON
Schema rather than being free text.

Failures do not crash the graph computation.  Each exception log e_i is
converted into natural-language context and fed back for local parameter
correction and retry at the current node (Eq. 3), capped at K attempts —
the "invocation-validation-retry" micro-cycle.
"""
import datetime
import json
import time
from typing import Any, Dict, List

from ..config import config
from ..llm import LLM
from ..tools import ToolExecutionError, ToolRegistry
from .schemas import (Observation, StructuredTask, TaskGraph, TaskNode,
                      ToolCallRecord)

_SYSTEM = """\
You are the execution module of an urban life agent working on ONE atomic
sub-task of a larger plan. Ground every fact in tool observations — never
invent values. Use ONLY the provided tools.

Hard constraints of the overall task (respect them when choosing arguments):
%s

Geocoding discipline: when resolving a place to coordinates, use its FULL
official name. Inspect every geocode result before accepting it — if you asked
for a specific POI (an airport, railway station, university, mall, scenic spot,
hospital, government office, etc.) but the result is a COARSE ADMINISTRATIVE
match (its `level` is a province / city / district / township / street, or its
formatted address does not actually contain the place you asked for), the
geocoder matched the WRONG entity. Do not accept it: re-geocode with the full
official name (e.g. "重庆江北国际机场", not "重庆江北机场"; "北京首都国际机场",
not "首都机场") before proceeding.

City/region match (critical — validate before using any geocode result): a
geocode result carries a province / city / district. If that city/province does
NOT match the target city named in the query — e.g. you asked for a place in
杭州 but the result's city is 黄冈市 / 湖北省 — then maps_geo resolved a WRONG,
same-name-elsewhere entity. NEVER use such a coordinate (it produces absurd
cross-province routes/distances). Instead resolve the place with maps_text_search
scoped to the correct city (pass city=<target city>), pick the POI that matches,
and read its coordinate (via maps_search_detail when the search result lacks one).
For a landmark / named venue / POI (a plaza, temple, fountain, mall, park,
station, scenic spot...), PREFER maps_text_search over a bare maps_geo call from
the start — geocoding a bare landmark name frequently lands in the wrong city,
whereas a city-scoped POI search does not.

Provider coverage: the amap/高德 tools (maps_geo, maps_regeo, maps_text_search,
maps_around_search, maps_weather, maps_ip_location) cover MAINLAND CHINA ONLY.
For a place outside mainland China (e.g. a US / overseas address or coordinate)
they will error or return a wrong coarse match — do NOT re-try the same amap
tool with reworded arguments for such a place. Switch to a provider that covers
that region if one exists, otherwise reply `FAILED:` for this sub-task rather
than burning retries on a provider that structurally cannot serve it.

Candidate selection discipline: when the sub-task is to SELECT or FILTER POIs by
a threshold attribute (rating ≥ X, price ≤ Y, distance ≤ D), you MUST obtain that
attribute — call maps_search_detail on EACH returned candidate's id — for every
candidate that could plausibly qualify BEFORE concluding "none qualifies". Do not
check only the first few and give up while other candidates from the same search
result are still unchecked (the qualifying one is often further down the list).
Conversely, do NOT spend maps_search_detail on the origin / reference location or
on POIs that are not answer candidates — detail only the candidates you rank.

When you have enough tool observations to fulfil this sub-task, reply with a
plain-text observation summary starting with `OBSERVATION:` followed by the
key facts (include exact numbers, ids, coordinates so later steps can reuse
them). If, after using the tools, the sub-task is genuinely impossible, reply
`FAILED:` with the reason.
"""



def _now_dt():
    """测试复现用: URBAN_AGENT_NOW 覆盖当前时间(如 2026-07-11), 否则真实now。"""
    import os, datetime as _dt
    fake = os.environ.get("URBAN_AGENT_NOW")
    if fake:
        try: return _dt.datetime.fromisoformat(fake)
        except ValueError: return _dt.datetime.strptime(fake[:10], "%Y-%m-%d")
    return _dt.datetime.now()

def _preview(value: Any, limit: int = 800) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text[:limit] + ("..." if len(text) > limit else "")


def _is_zero_count(result: Any) -> bool:
    """HTTP-success payload whose authoritative answer is count==0 (e.g. USGS)."""
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except Exception:
            return False
    if isinstance(result, dict) and "count" in result:
        try:
            return float(result.get("count")) == 0.0
        except (TypeError, ValueError):
            return False
    return False


def _is_empty(result: Any) -> bool:
    """A tool call that SUCCEEDED but carried no usable payload (empty search /
    geocode). Zero-count earthquake tallies are NOT empty — see _is_zero_count.
    UrbanAgent must not silently accept empty lists as the answer — it re-queries
    with adjusted arguments (see _execute_node)."""
    if _is_zero_count(result):
        return False
    if result is None:
        return True
    if isinstance(result, str):
        s = result.strip()
        if not s:
            return True
        try:
            result = json.loads(s)
        except Exception:
            return False          # non-empty free text carries content
    if isinstance(result, (list, tuple, set)):
        return len(result) == 0
    if isinstance(result, dict):
        if not result:
            return True
        if "count" in result and str(result.get("count")).strip() in ("0", "0.0"):
            return True
        for k in ("pois", "geocodes", "results", "tips", "districts"):
            if k in result and result[k] in (None, [], {}, ""):
                return True
    return False


def _geo_wrong_city(name: str, arguments: Dict[str, Any], result: Any) -> bool:
    """maps_geo matched a same-name entity in the WRONG city. The planner passes
    the target city in `city`; amap sometimes ignores it and geocodes the bare
    name elsewhere (e.g. "恒山景区" city="大同" -> 黑龙江鸡西市恒山区). Detect it
    so execution can reject and re-resolve via POI search instead of routing to a
    coordinate 2000km away. Only fires for maps_geo with a stated city."""
    if name != "maps_geo":
        return False
    city = str((arguments or {}).get("city") or "").strip()
    key = city.rstrip("市区县省")
    if not key:
        return False
    r = result
    if isinstance(r, str):
        try:
            r = json.loads(r)
        except Exception:
            return False
    if not isinstance(r, dict):
        return False
    items = r.get("return") or r.get("geocodes")
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        return False
    top = items[0]
    blob = "".join(str(top.get(k) or "") for k in
                   ("province", "city", "district", "formatted_address"))
    return key not in blob


def _node_prompt(node: TaskNode, upstream: List[Observation]) -> str:
    parts = ["Sub-task %s: %s" % (node.id, node.description)]
    if node.args_template:
        parts.append("Argument template (resolve placeholders from upstream "
                     "observations): %s" % json.dumps(node.args_template, ensure_ascii=False))
    if upstream:
        parts.append("Upstream observations O_<i. COPY coordinates / ids / dates from "
                     "their structured `data` EXACTLY — do not re-derive or re-geocode "
                     "a location whose coordinate is already available upstream:")
        for ob in upstream:
            parts.append("- [%s] %s" % (ob.node_id, ob.summary or ""))
            if ob.data is not None:
                parts.append("    data[%s]: %s" % (ob.node_id, _preview(ob.data, 900)))
    return "\n".join(parts)


def execute_graph(llm: LLM, task: StructuredTask, graph: TaskGraph,
                  registry: ToolRegistry,
                  observations: Dict[str, Observation] = None) -> Dict[str, Observation]:
    hard = json.dumps([c.model_dump() for c in task.hard_constraints],
                      ensure_ascii=False) or "[]"
    system = _SYSTEM % hard
    # Temporal grounding: the agent must know "now" to resolve relative time
    # windows (过去1个月 / 近30小时 / 明天) into the concrete start/end parameters
    # a tool needs. Without an anchor the model silently drops the time filter
    # (e.g. counting all-time earthquakes instead of the past month).
    system = ("Current date and time: %s (local). Unless the query states an "
              "explicit absolute date, resolve every relative time expression "
              "(过去N天 / 近N小时 / 最近 / 明天 / 后天) into concrete ABSOLUTE start "
              "and end date-times anchored to this current time, pass them as the "
              "tool's time parameters (startTime/endTime or equivalent), and apply "
              "the SAME resolved window to every tool call that needs it — never "
              "omit the time filter for a time-bounded query.\n\n"
              % _now_dt().strftime("%Y-%m-%d %H:%M %A")) + system
    # Caller may pass a sink dict so that partial progress survives a
    # BudgetExceeded raised mid-execution (the completed nodes are already in it).
    if observations is None:
        observations = {}

    for node in graph.topological_order():
        # Adaptive re-planning grows one shared graph across rounds; nodes already
        # executed in a prior round keep their observation and are not re-run.
        if node.id in observations:
            continue
        upstream = [observations[d] for d in node.depends_on if d in observations]
        observations[node.id] = _execute_node(llm, system, node, upstream, registry)
    return observations


def _execute_node(llm: LLM, system: str, node: TaskNode,
                  upstream: List[Observation], registry: ToolRegistry) -> Observation:
    ob = Observation(node_id=node.id)
    schemas = registry.schemas(node.tool_candidates)
    expanded = False      # full-library fallback opened after repeated failures
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": _node_prompt(node, upstream)},
    ]
    failures = 0          # counts failed invocations -> retry budget K
    total_calls = 0       # guards runaway loops
    # Candidate-exhaustion node (fetches per-candidate details to filter by a
    # rating/price/distance threshold): do NOT finalize after the first batch —
    # check EVERY returned candidate and ACCUMULATE all details, so the filter
    # sees the qualifying one in a single node instead of leaving it to costly
    # multi-round re-planning (and instead of losing all but the last detail).
    detail_node = "maps_search_detail" in (node.tool_candidates or [])
    call_cap = 8 if detail_node else config.max_tool_calls_per_node
    collected: List[Any] = []

    while True:
        msg = llm.chat(messages, tools=schemas, tool_choice="auto")
        tool_calls = getattr(msg, "tool_calls", None)

        if not tool_calls:
            text = (msg.content or "").strip()
            if text.upper().startswith("FAILED"):
                ob.status = "failed"
                ob.summary = text
            else:
                ob.summary = text.split("OBSERVATION:", 1)[-1].strip() or text
            return ob

        messages.append({"role": "assistant", "content": msg.content,
                         "tool_calls": [tc.model_dump() for tc in tool_calls]})

        turn_ok = False
        for tc in tool_calls:
            name = tc.function.name
            t_start = time.time()
            try:
                arguments = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError as err:
                arguments, result, error = {}, None, "malformed arguments JSON: %s" % err
            else:
                try:
                    result, error = registry.invoke(name, arguments), None
                except ToolExecutionError as err:
                    result, error = None, str(err)

            total_calls += 1
            tool_obj = registry.get(name)
            record = ToolCallRecord(tool=name,
                                    server=getattr(tool_obj, "server", "local"),
                                    arguments=arguments,
                                    success=error is None,
                                    result_preview="" if error else _preview(result),
                                    raw_result=None if error else result,
                                    error=error, attempt=failures + 1,
                                    latency_seconds=round(time.time() - t_start, 3))
            ob.tool_calls.append(record)

            if error is None and not _is_empty(result) and _geo_wrong_city(name, arguments, result):
                # Geocoder matched a same-name entity in the WRONG city — do not
                # finalize on it (it yields absurd cross-province routes). Reject
                # and steer to a city-scoped POI search, exactly as a careful
                # agent (or the react baseline) recovers.
                failures += 1
                _city = (arguments or {}).get("city") or "the target city"
                content = ("GEOCODE MATCHED THE WRONG CITY: you requested city=%s but maps_geo "
                           "returned a same-name place in a DIFFERENT province/city. Do NOT use "
                           "this coordinate. Re-resolve with maps_text_search (pass city=%s and "
                           "the landmark keyword), then read the coordinate from the matching POI "
                           "(via maps_search_detail if the search result has no coordinate). "
                           "Remaining retries: %d"
                           % (_city, _city, max(config.max_retries_per_node - failures, 0)))
            elif error is None and not _is_empty(result):
                if detail_node and name == "maps_search_detail":
                    collected.append(result)
                    ob.data = collected       # accumulate EVERY candidate's detail
                else:
                    ob.data = result
                turn_ok = True
                content = _preview(result, 2000)
            elif error is None:
                # Call SUCCEEDED but returned empty. UrbanAgent does not accept an
                # empty return as the answer: re-query with adjusted args. Escape
                # hatch for legitimately-empty results (e.g. genuinely no earthquakes)
                # so valid "none" answers are not retried forever.
                failures += 1
                content = ("TOOL RETURNED EMPTY (no results / zero count / key list blank). "
                           "Do NOT accept this empty as the answer. If empty is a genuinely "
                           "valid result for this sub-task, reply `OBSERVATION:` stating that. "
                           "Otherwise the arguments were too narrow or wrong — relax the search "
                           "radius, broaden or replace the keyword, drop over-specific filters, "
                           "try an alternate name/spelling, or pick another candidate tool — and "
                           "retry to obtain non-empty data. Remaining retries: %d"
                           % max(config.max_retries_per_node - failures, 0))
            else:
                failures += 1
                # Eq. 3: exception log as natural-language retry context
                content = ("TOOL ERROR: %s\nCorrect the parameters (or pick another "
                           "candidate tool) and retry. Remaining retries: %d"
                           % (error, max(config.max_retries_per_node - failures, 0)))
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})

        if turn_ok and detail_node and total_calls < call_cap:
            # Candidate-exhaustion: do NOT finalize yet — keep checking every
            # returned candidate so the threshold filter does not conclude "none
            # qualifies" while a qualifying candidate sits further down the list.
            n_checked = sum(1 for c in ob.tool_calls
                            if c.tool == "maps_search_detail" and c.success)
            messages.append({"role": "user", "content":
                "已核验 %d 个候选的详情。搜索结果通常按相关性/距离排序,合格候选一般靠前——"
                "请对【最相关的前几个尚未核验】的候选继续 maps_search_detail(总共核验约 5-8 个"
                "最有希望的即可,不必穷尽全部)。一旦找到满足阈值的候选,或已核验完最相关的若干个,"
                "就回复 `OBSERVATION:` 给出满足条件的候选(含关键属性)或说明无一满足。" % n_checked})
            # fall through: loop for another turn instead of finalizing
        elif turn_ok:
            # (a2) atomic-node fast path: a planned node is one tool action, so
            # once a tool call in this turn succeeds we finalize deterministically
            # instead of spending another LLM call just to narrate the result.
            # Downstream nodes receive the structured `data`; synthesis re-reasons
            # over all observations. All-failed turns fall through to closed-loop
            # retry (Eq. 3), preserving fault tolerance.
            last = next((c for c in reversed(ob.tool_calls) if c.success), None)
            ob.summary = ("OBSERVATION from %s: %s" % (last.tool, _preview(ob.data, 400))
                          if last else (ob.summary or ""))
            return ob

        if not turn_ok and failures >= 2 and not expanded:
            # Adaptation on observed errors: the planned candidates keep
            # failing, so open the FULL tool library — the model may switch to
            # a tool whose provider actually covers this location/domain
            # instead of rewording arguments for one that cannot serve it.
            schemas = registry.schemas()
            expanded = True
            messages.append({"role": "user", "content":
                "The planned candidate tools keep failing on this sub-task. "
                "The FULL tool library is now available to you. Re-read the "
                "errors above, pick a tool whose provider actually covers this "
                "location/domain, and continue. If the sub-task's value is "
                "already known from the query or upstream observations, reply "
                "`OBSERVATION:` with it. If no tool can help, reply `FAILED:`."})

        if failures > config.max_retries_per_node:
            ob.status = "failed"
            ob.summary = "FAILED: exceeded retry budget K=%d; last error: %s" % (
                config.max_retries_per_node,
                next((c.error for c in reversed(ob.tool_calls) if c.error), "unknown"))
            return ob
        if total_calls >= call_cap:
            # force the model to wrap up with what it has
            messages.append({"role": "user",
                             "content": "Tool budget exhausted. Summarize what you "
                                        "observed as `OBSERVATION:` now."})
            msg = llm.chat(messages)
            ob.summary = (msg.content or "").split("OBSERVATION:", 1)[-1].strip()
            return ob
