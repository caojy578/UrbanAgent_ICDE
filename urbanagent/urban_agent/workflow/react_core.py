# -*- coding: utf-8 -*-
"""ReAct-style execution core for UrbanAgent (v2 backbone).

Replaces the rigid plan-then-execute DAG (planning.py + execution.py) with a
single adaptive reason->act->observe loop over the FULL tool surface — the same
mechanic that makes the strongest baseline (LangGraph create_react_agent)
robust on exploration-heavy urban tasks — while keeping UrbanAgent's
distinctive value-adds layered on top:

  * urban tool-applicability grounding (China-only providers; coordinate-less
    POI search must be followed by maps_search_detail; prefer city-scoped POI
    search over bare geocoding of a landmark);
  * deterministic geo wrong-city rejection (Eq.-3 style natural-language retry);
  * "no empty as answer" re-query;
  * candidate-exhaustion discipline before concluding "none qualifies";
  * persistence: do not stop before the observations support an answer.

The loop records EVERY tool invocation as an Observation (nodes t1, t2, ...) so
the trace still feeds UrbanEval's process-layer metrics (tool-invocation
completeness / order accuracy / efficiency) uniformly with the baselines. The
loop's own final natural-language answer is returned alongside the observations
and used as a draft answer. In the reported configuration, synthesis rewrites
that draft to align it with the task and collected observations.
"""
import datetime
import json
import time
from typing import Any, Dict, List, Optional, Tuple

from types import SimpleNamespace

from ..config import config
from ..llm import LLM, _extract_json, LLMError
from ..tools import ToolExecutionError, ToolRegistry
from .cognition import format_task
from .execution import _geo_wrong_city, _is_empty, _is_zero_count, _preview
from .schemas import Observation, StructuredTask, ToolCallRecord

_REACT_SYSTEM = """\
You are an urban-life agent that answers the user's request by calling the
provided tools in an adaptive reason -> act -> observe loop. Ground every fact
in tool observations — never invent values. Answer in the SAME language as the
user's request.

Structured understanding of the task (intent, entities, hard/soft constraints):
%s

Available tools (Tool Metadata):
%s

How to work:
- Decide the next single most useful tool call, make it, read the result, then
  decide again. Retrieve candidates before fetching their details; check a
  condition (e.g. weather) before the branch that depends on it. Do BOTH branches
  of a conditional ("if it rains ... else ...") enough to compare, then decide.
- NEVER repeat a tool call you have already made with the same (or equivalent)
  arguments — its result is ALREADY in this conversation above. Re-read that
  result instead of calling again. A forecast/search/route result you already
  fetched does not change on a second identical call; the required value (e.g. a
  09:00–12:00 rain probability) is inside the long payload you already have —
  locate it there and USE it. Each new tool call must obtain genuinely NEW
  information (a different place, a different route mode, a still-missing value).
- PERSIST on GENUINELY-MISSING information only: keep going until every hard
  constraint and the user's full intent is covered — but "persist" means fetch
  the NEXT missing piece, never re-fetch what you already have. The moment the
  observations already answer the task, STOP calling tools and give the answer.
  Only give up on a genuinely impossible sub-goal, and say why.

Urban tool-applicability (judge each tool from its metadata):
- BEFORE calling a tool, match what it NEEDS against what the query already GIVES.
  If the query already states a value that a tool would otherwise compute (e.g. it
  says "两地相距约1.2公里" / "6.8公里"), USE that stated value directly as the input
  to the downstream tool (the carbon/emission tool's distance) — do NOT first run a
  routing tool just to re-derive a distance the user handed you. Read each tool's
  required parameters, fill them from the query's given facts, and only call a tool
  when it adds something the query did not already provide and the task needs.
- The amap/高德 tools (maps_geo, maps_regeo, maps_text_search, maps_around_search,
  maps_weather, maps_direction_*, maps_ip_location) cover MAINLAND CHINA ONLY. For
  a place outside mainland China they error or return a wrong coarse match — switch
  to a provider that covers that region, or state the limitation; do not burn calls
  re-wording arguments for a provider that structurally cannot serve the location.
- FOREIGN (non-China) trip: do NOT attempt amap geocoding/routing for US/overseas
  places at all — it cannot serve them. For a carbon/emission request there, take
  the user-stated distance and vehicle type and compute emissions directly via the
  emission tool; for reviews use the US-capable provider (e.g. Yelp); for weather
  use the global weather tool for the current/near window it supports. Never fail
  the task chasing a China-only coordinate that the query does not need.
- maps_text_search / maps_around_search return POIs WITHOUT coordinates (only id,
  name, address). To route to / measure distance to a chosen POI you MUST first
  call maps_search_detail on its id and read the coordinate from there.
- For a landmark / named venue / POI (plaza, temple, mall, station, park, scenic
  spot, hospital, airport...), PREFER a city-scoped maps_text_search (pass
  city=<target city>) over a bare maps_geo — geocoding a bare landmark name often
  lands in the WRONG same-name city.

Discipline that separates a careful agent from a careless one:
- CITY/REGION match: after any maps_geo, check the result's province/city/district
  actually matches the target city in the query. If not (e.g. asked for a place in
  杭州 but got 湖北/黄冈), it matched a wrong same-name entity — DISCARD that
  coordinate and re-resolve via city-scoped maps_text_search + maps_search_detail.
  A cross-province coordinate yields absurd routes/distances.
- NEVER accept an EMPTY tool result (no results / zero count) as the answer: relax
  the radius, broaden/replace the keyword, try an alternate name/spelling, or pick
  another tool, and retry — unless empty is genuinely the correct answer, then say so.
- ADDRESS granularity: when asked for a detailed address, report the FULL admin
  hierarchy the tools return (province -> city -> district/县级市 -> street/门牌)
  and a nearby named landmark if the finest field is coarse; do not stop at city.
  When you use a nearby POI (maps_around_search) as the landmark for a reverse-
  geocoded point, VERIFY the POI's own city/district matches the reverse-geocode
  result — REJECT a POI whose address is in a DIFFERENT city (e.g. reverse-geocode
  says 武汉江岸区 but the nearest POI's address is in 仙桃): it is a mislabeled/
  distant entry, not a valid landmark; widen the radius or fall back to the
  reverse-geocode's own street/township instead of naming a wrong-city POI.
- COORDINATE datum: report coordinates EXACTLY as the tool returns them. The amap
  tools return GCJ-02; the evaluation uses the provider's native datum. Do NOT
  convert between coordinate systems (no GCJ-02 <-> WGS-84 conversion) — a
  conversion shifts the point by hundreds of metres and fails the tolerance.
- SELECTION by threshold (rating ≥ X, price ≤ Y, distance ≤ D): obtain that
  attribute (maps_search_detail) for EVERY plausibly-qualifying candidate before
  concluding "none qualifies" — the qualifying one is often further down the list.
  Do not waste detail calls on the origin/reference point.
- RELATIVE criterion ("评分较高 / 高于平均 / better than typical / 性价比高"): a
  relative quality claim needs a BASELINE. Fetch a set of comparable candidates in
  the area (enough to be representative), read their ratings/prices, compute the
  average (or a clear typical level), then pick the ones ABOVE it and STATE the
  comparison explicitly ("X 评分 4.6,高于该区咖啡馆均值 4.1"). Do not just return a
  few high-rated names without establishing what "high" is measured against.
- COMMIT: once the observations support an answer, STATE it directly and
  completely — concrete numbers, coordinates as explicit lon,lat, names, the full
  address, the computed comparison. If a well-known fact (e.g. a hospital's
  三甲 grade) is not in a tool field but the chosen entity clearly satisfies the
  filter, say so with the evidence you have; note any single imperfect detail in
  one clause rather than withholding the whole answer.
- COMMIT the FULL result, not a teaser: when the query asks how many / for a list
  of records (e.g. earthquakes in a window), give BOTH the count AND the itemized
  records (each with its key fields) — never answer with only a count and offer
  "shall I list them?". When asked for an address, commit the FINEST-granularity
  value you obtained (street/门牌/named landmark) AS the answer, not merely the
  district.
- NO DEFERRAL — this is critical. If the query asks for something (an address, a
  price/收费, a list, a chosen recommendation) and the tools can supply it, you
  MUST supply it in THIS final answer. Do NOT list candidates and then ask the
  user "which one?" — pick and state the best one yourself. Do NOT answer part of
  the query and offer the rest as a next step ("要我继续查收费吗 / A/B/C 你选哪个 /
  请告诉我下一步"): if a required detail (e.g. 收费标准, a POI's street) is not yet
  in your observations, MAKE the extra tool call to fetch it BEFORE answering; only
  if it is genuinely absent from every tool do you say so in one clause. NEVER end
  the final answer with a question offering to do what the query already asked —
  the answer must be self-contained and actionable as-is. A trailing "shall I…?"
  when you already have (or could fetch) the data is a FAILURE to answer.

When the request is fully answered, reply with plain text (no tool call): a
complete, committed, self-contained final answer in the user's language — no
"next step" questions about things the query already asked for.
"""

_TEXT_INVOKE = """
You do not have a native function-calling interface. Tool names, coverage, and
input fields are listed above. To invoke a tool, reply with ONLY a JSON object:
{"name": "<exact tool name>", "arguments": { ... }}
To finish, reply with ONLY:
{"final": "<complete answer in the user's language>"}
Do not mix prose with the JSON. Actual services still enforce their own field
types; a malformed or incomplete argument object will fail at execution.
"""


def _parse_text_action(content: str):
    """Return ({type: final|call, ...}, parse_error_or_None)."""
    try:
        data = _extract_json(content or "")
    except LLMError as err:
        return None, str(err)
    if not isinstance(data, dict):
        return None, "JSON root is not an object"
    if "final" in data and data.get("name") is None and data.get("tool") is None:
        return {"type": "final", "text": str(data.get("final") or "").strip()}, None
    name = data.get("name") or data.get("tool")
    if not name:
        return None, "JSON has neither name/tool nor final"
    args = data.get("arguments") if isinstance(data.get("arguments"), dict) else {}
    return {"type": "call", "name": str(name), "arguments": args}, None


def _invoke_diag(registry: ToolRegistry, name: str, arguments: dict, error: str) -> str:
    if error is None:
        return "ok"
    canonical = registry.resolve(name)
    if canonical is None:
        return "unknown_tool"
    tool = registry.get(canonical)
    required = set((tool.parameters or {}).get("required") or []) if tool else set()
    missing = [k for k in required if k not in (arguments or {})]
    if missing:
        return "missing_required"
    err = (error or "").lower()
    if "malformed arguments json" in err:
        return "json_parse"
    if "parameter error" in err or "typeerror" in err:
        return "type_error"
    return "service_error"



def _now_dt():
    """测试复现用: URBAN_AGENT_NOW 覆盖当前时间(如 2026-07-11), 否则真实now。"""
    import os, datetime as _dt
    fake = os.environ.get("URBAN_AGENT_NOW")
    if fake:
        try: return _dt.datetime.fromisoformat(fake)
        except ValueError: return _dt.datetime.strptime(fake[:10], "%Y-%m-%d")
    return _dt.datetime.now()

def _compact_messages(messages: List[Dict[str, Any]], cap: int = 2500) -> List[Dict[str, Any]]:
    """Persist the ReAct transcript for scoring; cap bulky tool payloads."""
    out: List[Dict[str, Any]] = []
    for m in messages:
        item: Dict[str, Any] = {"role": m.get("role")}
        content = m.get("content")
        if isinstance(content, str) and len(content) > cap:
            item["content"] = content[:cap] + "…[truncated %d chars]" % (len(content) - cap)
        else:
            item["content"] = content
        tcs = m.get("tool_calls")
        if tcs:
            compact_tcs = []
            for tc in tcs:
                if isinstance(tc, dict):
                    fn = tc.get("function") or {}
                    compact_tcs.append({
                        "id": tc.get("id"),
                        "name": fn.get("name"),
                        "arguments": fn.get("arguments"),
                    })
                else:
                    fn = getattr(tc, "function", None)
                    compact_tcs.append({
                        "id": getattr(tc, "id", None),
                        "name": getattr(fn, "name", None),
                        "arguments": getattr(fn, "arguments", None),
                    })
            item["tool_calls"] = compact_tcs
        if m.get("tool_call_id"):
            item["tool_call_id"] = m.get("tool_call_id")
        out.append(item)
    return out


def run_react(llm: LLM, task: StructuredTask, registry: ToolRegistry,
              query: str, observations: Dict[str, Observation] = None,
              transcript: Optional[List[Dict[str, Any]]] = None) -> Tuple[Dict[str, Observation], str]:
    """Whole-task ReAct loop. Returns (observations, final_answer_text).

    The caller may pass an ``observations`` sink dict so that partial progress
    (every tool call made so far) survives a BudgetExceeded raised mid-loop —
    the completed observations are already in it, feeding the process metrics
    uniformly with the baselines."""
    now = _now_dt().strftime("%Y-%m-%d %H:%M %A")
    hard = json.dumps([c.model_dump() for c in task.hard_constraints],
                      ensure_ascii=False) or "[]"
    system = _REACT_SYSTEM % (format_task(task), registry.catalog())
    if config.invoke_mode == "text_json":
        system = system + _TEXT_INVOKE
    system = ("Current date and time: %s (local). Resolve every relative time "
              "expression (过去N天 / 近N小时 / 最近 / 明天 / 后天) into concrete "
              "ABSOLUTE start/end date-times anchored to this current time (or to "
              "the stated departure time when the request pins one), pass them as "
              "the tool's time parameters, and apply the SAME window to every "
              "time-bounded call. YEAR for a bare month-day: a date written without "
              "a year (e.g. '7月12号', '10月1到5号') refers to THIS current year — a "
              "booking/travel plan the user is stating now. Do NOT roll it forward to "
              "NEXT year just because the month-day is a few days before today; only "
              "use next year if the query explicitly names a future year or the "
              "month-day is many months in the past. Pass this current-year date to "
              "every hotel/room/booking/route tool.\n\nHard constraints: %s\n\n"
              % (now, hard)) + system

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": query},
    ]
    schemas = None if config.invoke_mode == "text_json" else registry.schemas()
    if observations is None:
        observations = {}
    seq = len(observations)
    final_text = ""
    # Two DISTINCT guards, because a repeated SUCCESS and a repeated FAILURE are
    # opposite problems:
    #  * succeeded — signatures (tool + args) that already returned VALID data.
    #    Repeating one is pure waste (its result cannot change and is already in
    #    the conversation), so it is blocked — this is what stopped the 21x
    #    forecast re-poll.
    #  * fail_count — FAILED / empty attempts per tool. These are NOT blocked:
    #    retrying a transient failure (same or corrected args) is legitimate and
    #    often succeeds, so we allow a GENEROUS number before merely NUDGING the
    #    model to switch tools. We never hard-stop a retry the way a success-repeat
    #    is hard-stopped.
    succeeded: set = set()
    fail_count: Dict[str, int] = {}
    FAIL_CAP = 8                       # retries allowed per tool before a switch nudge
    # Upper bound on reason-act turns; the real ceiling is the LLM call budget
    # (BudgetExceeded is raised by llm.chat and propagates to the agent).
    max_turns = max(2, 2 * config.max_llm_calls_per_query)

    def _snap_transcript() -> None:
        if transcript is None:
            return
        transcript[:] = _compact_messages(messages)

    for _turn in range(max_turns):
        # When the per-query LLM-call budget is nearly spent, force a committed
        # answer: call WITHOUT tools so the model must reply in text (instead of
        # burning the last call on yet another tool request and returning empty).
        remaining = (llm.max_calls - llm.usage["calls"]) if getattr(llm, "max_calls", None) else None
        near_calls = remaining is not None and remaining <= 2
        # Wall-clock backstop: slow tool backends (e.g. USGS / Climatiq on the US
        # queries) can exhaust the per-query time budget long before the LLM-call
        # budget. Force a committed answer while there is still time, so a slow
        # query yields a real answer instead of being killed empty by the watchdog.
        deadline = getattr(llm, "deadline", None)
        near_time = deadline is not None and time.time() >= deadline - 90
        force_final = near_calls or near_time
        if force_final:
            messages.append({"role": "user", "content":
                "Tool-call budget is nearly exhausted. STOP calling tools and give "
                "your COMPLETE final answer NOW, in the user's language, committing "
                "to the best-supported conclusion from the observations you already "
                "have (state any single missing detail in one clause)."})
        msg = llm.chat(messages, tools=None if force_final else schemas,
                       tool_choice=None if force_final else "auto")
        tool_calls = None
        text_json_turn = (config.invoke_mode == "text_json" and not force_final)
        if text_json_turn:
            parsed, parse_err = _parse_text_action(msg.content or "")
            messages.append({"role": "assistant", "content": msg.content})
            if parse_err:
                seq += 1
                observations["t%d" % seq] = Observation(
                    node_id="t%d" % seq, status="failed",
                    summary="text_json parse error",
                    tool_calls=[ToolCallRecord(
                        tool="", success=False, error=parse_err,
                        diag="json_parse")])
                messages.append({"role": "user", "content":
                    "Your reply was not valid tool JSON (%s). Reply with ONLY "
                    "{\"name\": \"...\", \"arguments\": {...}} or {\"final\": \"...\"}."
                    % parse_err})
                continue
            if parsed["type"] == "final":
                final_text = parsed["text"]
                break
            tool_calls = [SimpleNamespace(
                id="text_%d" % (seq + 1),
                function=SimpleNamespace(
                    name=parsed["name"],
                    arguments=json.dumps(parsed["arguments"], ensure_ascii=False)))]
        else:
            tool_calls = None if force_final else getattr(msg, "tool_calls", None)
            if not tool_calls:
                final_text = (msg.content or "").strip()
                break
            messages.append({"role": "assistant", "content": msg.content,
                             "tool_calls": [tc.model_dump() for tc in tool_calls]})
        for tc in tool_calls:
            name = tc.function.name
            t_start = time.time()
            try:
                arguments = json.loads(tc.function.arguments or "{}")
                sig = (name, json.dumps(arguments, sort_keys=True, ensure_ascii=False, default=str))
            except json.JSONDecodeError:
                arguments, sig = {}, None
            # Block ONLY a redundant repeat of a call that ALREADY SUCCEEDED — its
            # result is unchanged and already above. A FAILED signature is NOT here,
            # so retrying a transient failure is never blocked by this guard.
            if sig is not None and sig in succeeded:
                messages.append({"role": "tool", "tool_call_id": tc.id, "content":
                    ("This exact %s call already SUCCEEDED earlier; its result is in the "
                     "conversation above — re-read it, do NOT call it again. Move on to a "
                     "DISTINCT next step (a different place/mode/value) or give your final "
                     "answer." % name)})
                continue
            if sig is None:
                result, error = None, "malformed arguments JSON"
            else:
                try:
                    result, error = registry.invoke(name, arguments), None
                except ToolExecutionError as err:
                    result, error = None, str(err)

            seq += 1
            node_id = "t%d" % seq
            tool_obj = registry.get(name)
            record = ToolCallRecord(
                tool=name, server=getattr(tool_obj, "server", "local"),
                arguments=arguments, success=error is None,
                result_preview="" if error else _preview(result),
                raw_result=None if error else result, error=error,
                attempt=1, latency_seconds=round(time.time() - t_start, 3))
            ob = Observation(node_id=node_id, tool_calls=[record],
                             status="ok" if error is None else "failed")

            record.diag = _invoke_diag(registry, name, arguments, error)

            if not config.obs_recovery:
                # Ablation: raw payload / raw error only. Dedup + budget stay.
                if error is None:
                    ob.data = result
                    ob.summary = "raw observation from %s" % name
                    content = _preview(result, 2000)
                    if not content:
                        content = json.dumps(result, ensure_ascii=False, default=str)[:2000]
                    if sig is not None and not _is_empty(result):
                        succeeded.add(sig)
                else:
                    ob.status = "failed"
                    ob.summary = "raw error from %s" % name
                    content = error
            elif error is None and not _is_empty(result) and _geo_wrong_city(name, arguments, result):
                _city = (arguments or {}).get("city") or "the target city"
                ob.status = "failed"
                ob.summary = "geocode matched wrong city"
                content = ("GEOCODE MATCHED THE WRONG CITY: you requested city=%s but "
                           "maps_geo returned a same-name place in a DIFFERENT "
                           "province/city. Do NOT use this coordinate. Re-resolve with "
                           "maps_text_search (city=%s + landmark keyword), then read the "
                           "coordinate from the matching POI (maps_search_detail if the "
                           "search result has no coordinate)." % (_city, _city))
            elif error is None and not _is_empty(result):
                ob.data = result
                ob.summary = "OBSERVATION from %s" % name
                content = _preview(result, 2000)
                if sig is not None:
                    succeeded.add(sig)        # valid data — block only identical repeats
            elif error is None and _is_zero_count(result):
                ob.data = result
                ob.status = "ok"
                ob.summary = "count=0 from %s (valid tally)" % name
                content = _preview(result, 2000)
                if sig is not None:
                    succeeded.add(sig)
                content += (
                    "\n[note] Tool returned count=0 for these parameters — this is a "
                    "successful observation. You MAY state zero occurrences in your "
                    "answer. Only broaden/retry if the region/time/magnitude filters "
                    "do not match the user's query.")
            elif error is None:
                ob.status = "failed"
                ob.summary = "empty result from %s" % name
                content = ("TOOL RETURNED EMPTY (no candidates / no rows). Do NOT treat "
                           "this as a final answer unless you have verified the filters "
                           "match the query. Otherwise relax the radius, broaden or "
                           "replace the keyword, drop over-specific filters, try an "
                           "alternate name/spelling, or another tool, and retry.")
            else:
                ob.summary = "error from %s: %s" % (name, error)
                content = ("TOOL ERROR: %s\nThis may be transient — you MAY retry the SAME "
                           "call (a failed call is not cached), or correct the parameters, "
                           "or pick another tool." % error)

            # A failed / empty call is a legitimate retry candidate: count it and
            # only NUDGE (never block) once a single tool has failed many times, so
            # a flaky-but-correct call still gets ample attempts to succeed.
            if config.obs_recovery and ob.status == "failed":
                fail_count[name] = fail_count.get(name, 0) + 1
                if fail_count[name] >= FAIL_CAP:
                    content += ("\n[note] %s has now failed %d times. If the arguments are "
                                "already correct it may be a persistent outage — consider a "
                                "different tool/provider, or report this sub-goal as blocked."
                                % (name, fail_count[name]))

            observations[node_id] = ob
            if text_json_turn:
                messages.append({"role": "user", "content":
                    "Tool %s returned:\n%s" % (name or "(invalid)", content)})
            else:
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})
        _snap_transcript()

    # Record the loop's committed answer as a terminal observation so synthesis
    # (and the trace) can see the reasoning the tool results were combined into.
    if final_text:
        observations["answer"] = Observation(
            node_id="answer", data=final_text, summary=final_text, status="ok")
    _snap_transcript()
    return observations, final_text
