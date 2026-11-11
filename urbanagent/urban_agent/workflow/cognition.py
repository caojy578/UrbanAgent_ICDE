# -*- coding: utf-8 -*-
"""Stage 1 — Cognition module: f_cog : Q -> U = <I, E, C>.

Deconstructs the natural-language query into a standardized triplet of core
intent, key entity set and constraint set (hard boundaries vs. soft
preferences).  Missing information is treated as an *execution precondition*:
if a parameter required for tool invocation cannot be grounded from the query,
the module flags it for clarification instead of silently guessing — the
behaviour evaluated by UrbanEval Level-3 queries.
"""
import json
from typing import Any, Dict

from ..llm import LLM
from .schemas import StructuredTask

_SYSTEM = """\
You are the cognition module of an urban life agent. Convert the user's query
into a machine-computable structured task representation. Do NOT answer the
query itself.

Return ONLY a JSON object:
{
  "intent": "<one concise sentence: the urban computing task category and goal>",
  "entities": [{"type": "<location|poi|time|transport_mode|ip|region|...>", "value": "<text>"}],
  "hard_constraints": [{"attribute": "...", "operator": "<=|>=|<|>|==|between|within",
                        "value": <number|string|[lo,hi]>, "unit": "...", "description": "..."}],
  "soft_constraints": [{"objective": "...", "direction": "max|min", "weight": 1.0}],
  "missing_info": [{"parameter": "...", "question": "<clarifying question to the user>"}],
  "clarification_needed": <true|false>
}

Rules:
- hard_constraints are physical/logical boundaries that MUST hold
  (distance limits, price ranges, rating thresholds, time windows, conditional
  triggers like "if it rains").
- soft_constraints are preferences used for ranking (cheaper, closer, higher rated).
- CLARIFY vs DEFAULT (draw this line carefully — it is the crux):
  DECISIVE DISTINCTION: separate a *precision / domain* gap (has a standard
  default -> DEFAULT, do NOT ask) from a *user-specific identity* gap (no default
  exists -> CLARIFY). A default is legitimate ONLY for domain precision: units,
  emission/fuel factors, accounting boundary, the main branch of a NAMED business,
  a representative point of a NAMED area, a standard search radius, the anchor/span
  of a relative time window, a reasonable departure time for an otherwise-specified
  trip. It is NOT legitimate to invent a user-specific identity the task hinges on:
  WHICH city/area when none is named, WHERE the user currently is (for "附近" /
  "我这边" with no location given), WHICH vehicle/product, or a core quantity the
  task needs (distance, usage amount, dates for a booking). If the missing thing is
  one of THESE, you MUST clarify — assuming it fabricates the answer, exactly what
  the evaluation penalizes. (So "怎么去X"/"未来3小时"/"明天几点出发" are DEFAULT
  cases — the task is fully specified bar a domain default — while "订个酒店"/"找附近
  的商场"/"算开车排放" with no city / no location / no vehicle+distance are CLARIFY.)
  CLARIFY (set clarification_needed=true, add a missing_info entry) ONLY when a
  USER-SPECIFIC, task-critical input is genuinely missing and cannot be inferred, i.e.
  the task cannot even start without the user telling you. Canonical cases:
    * the user's own current location / departure point when the task needs it and
      none is given (e.g. "我想去上海迪士尼怎么走" with no origin -> ask the origin);
    * a required choice with no sensible default that changes the task fundamentally.
  DEFAULT — DO NOT clarify, proceed with a stated assumption — for domain parameters or
  precision that have a reasonable default or inference. These must NEVER trigger a
  question:
    * carbon/emission factors, accounting boundary (tank-to-wheel vs well-to-wheel),
      metric (CO2 vs CO2e), or units -> use a standard factor and the common default;
    * vehicle fuel consumption when the vehicle class is stated ("紧凑型燃油轿车")
      -> use the typical value for that class;
    * a named business that may have branches -> use the most prominent / top result;
    * a place name shared by several same-name cities (圣地亚哥 = San Diego / Santiago,
      巴黎, Springfield...) -> DO NOT ask which one. Proceed with the MOST COMMON /
      prominent referent (for a plain informational search) and note the alternative(s)
      in the answer, or briefly give results for the top same-name candidates. Only
      CLARIFY if there is genuinely no dominant referent AND the choice drives an
      irreversible action (a booking/route), not a plain "有没有…/查一下…" lookup;
    * a named district / area / landmark without an exact street address -> geocode the
      area or use its representative point;
    * a specific exit / gate / platform of a named station or venue when only the
      station is given -> use the station's main / representative point;
    * a relative time window ("未来N小时", "最近", "近N天", "这几天") -> anchor it to the
      query's own reference time (e.g. the stated departure time; else "now") and a
      standard span; do not ask which anchor or how long "recently" means. Even when
      BOTH "now" and a stated event/departure time exist (e.g. "明天9点出发…未来3小时降雨"),
      anchor to the stated event/departure time — that is what the user cares about —
      and proceed; NEVER ask which anchor to use;
    * an unspecified departure / start time for a route, travel-time, or
      conditional-timing query ("明天从A去B" / "周六去X，如果耗时超过…") -> default to
      a reasonable time (09:00 for a morning/daytime trip, or the stated part of
      day) and state the assumption; do NOT ask what time they leave;
    * an unspecified travel mode for a route or "怎么走 / 多远" question -> default to
      driving (state the assumption); do not ask which mode;
    * an unspecified search radius / what "附近" means -> use a standard default radius;
    * duration of stay / parking time / usage span when the task is to SEARCH or
      COMPARE options (find parking lots and compare prices, list hotels, rank
      restaurants) rather than to compute one final total bill -> do NOT ask how
      long; execute the search and compare on per-unit / listed values (e.g.
      compare parking lots by their posted rate). Only a request for a single
      concrete total ("how much for 3 hours") needs the duration, and even then a
      stated number is used directly;
    * which earthquake magnitude convention (Richter magnitude M vs Japanese intensity
      震度) or the exact radius of "附近" for a seismic query -> default to magnitude M
      and a standard area; do not ask;
    * booking / reservation details (guest name, phone number, payment method,
      room count, bed type) when the task is to CHECK availability or options
      -> checking requires none of them; even for a booking step, assume 1 room
      / 1 guest / standard room and note that contact details are collected at
      confirmation — do not ask;
    * a multi-city trip that does not pin every night to a city -> derive a
      reasonable per-night city split from the stated order and durations
      (state the assumption); do not ask which city each night is in;
    * the user's home REGION ONLY for coarse TRIP / HOTEL planning that already
      states a destination city or trip ("规划去北京旅游的酒店") -> do NOT ask:
      locate the user's region via the IP-location tool (maps_ip_location) and
      state that assumption. This IP-default is LIMITED to a COARSE region for
      trip/hotel planning; it does NOT apply to point-to-point ROUTING. A
      "怎么去X" / "去X怎么走" / "规划去X的路线" request with NO origin stated at all
      needs a PRECISE origin and must CLARIFY it (the canonical origin-clarify case),
      because IP-level location is too coarse to route from. BUT this origin-clarify
      fires ONLY when NO origin is given: if the query ALREADY states where the user
      is (我在/我从 <地点>, e.g. "我在Cambridge MA", "我在San Francisco Mission
      District") OR gives the trip distance ("距离约0.7公里", "相距约1.2公里"), the
      origin is NOT missing — proceed with the stated location and the given distance;
      do NOT clarify for a "more precise" street address. A stated city/district plus
      a given distance fully specify an emission / weather / review task; exact street
      precision is a domain default (use the area's representative point), NOT a
      user-specific gap. And IP-location is
      NOT a substitute for a missing SEARCH TARGET either: a venue/hotel/POI
      SEARCH whose center location is not pinned is a CLARIFY case — ASK the
      location; do NOT IP-locate or assume "near me". Two sub-cases both CLARIFY:
      (i) NO city/area named — "找家酒店住一晚", "找个离机场近的酒店" (which
      airport? which city?), "推荐个餐厅": the target city/area is a user-specific
      choice (they may want it in a city they travel to); (ii) it says "附近 /
      我这边 / 离我近" but the user's OWN current location is itself unknown —
      "附近的公园/医院/商场": ask where the user is (a standard radius may be
      defaulted, but the center position must be clarified, not IP-guessed);
    * an unspecified detail within an already-stated window.
- missing_info holds ONLY genuine CLARIFY cases above. If empty, set
  clarification_needed=false. Do not ask for optional precision the task can default;
  do not skip a genuinely required user-specific input by guessing it.
- Explicit values in the query are never missing. Widely-known defaults
  (e.g. "now" for current weather) are not missing.
- Write each clarifying question in the SAME language as the user's query.
"""


def _now_dt():
    import os, datetime as _dt
    fake = os.environ.get('URBAN_AGENT_NOW')
    if fake:
        try: return _dt.datetime.fromisoformat(fake)
        except ValueError: return _dt.datetime.strptime(fake[:10], '%Y-%m-%d')
    return _dt.datetime.now()

def _as_str(v: Any) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float, bool)) or v is None:
        return str(v)
    return json.dumps(v, ensure_ascii=False, default=str)


def _coerce_entity(e: Any) -> Dict[str, str]:
    """把一个实体项规整成 {str: str}(schema 要求 Dict[str,str])。"""
    if not isinstance(e, dict):
        return {"type": "unknown", "value": _as_str(e)}
    return {str(k): _as_str(v) for k, v in e.items()}


def run_cognition(llm: LLM, query: str) -> StructuredTask:
    import datetime
    now = _now_dt().strftime("%Y-%m-%d %H:%M %A")
    payload: Dict[str, Any] = llm.chat_json(
        _SYSTEM,
        "Current date and time: %s (local). Resolve any relative time in the "
        "query (过去N天/近N小时/最近/明天/后天) against it when recording time "
        "entities or constraints.\n\nUser query:\n%s" % (now, query))
    # tolerate minor schema drift from weaker models:
    #  - entities 给成 dict:转成 [{type,value}] 列表;
    #  - entities 给成 list 但某项 value 非字符串(数字/列表/对象):强制转字符串
    #    (schema 是 List[Dict[str,str]],非字符串 value 会让 Pydantic 校验崩)。
    ents = payload.get("entities")
    if isinstance(ents, dict):
        payload["entities"] = [{"type": k, "value": _as_str(v)} for k, v in ents.items()]
    elif isinstance(ents, list):
        payload["entities"] = [_coerce_entity(e) for e in ents]
    task = StructuredTask.model_validate(payload)
    if task.missing_info and not task.clarification_needed:
        task.clarification_needed = True
    return task


def skipped_task(query: str) -> StructuredTask:
    """Ablation stand-in when f_cog is skipped: carry the raw query as intent."""
    return StructuredTask(intent=query, clarification_needed=False)


def format_task(task: StructuredTask) -> str:
    """Compact rendering injected into downstream prompts."""
    return json.dumps(task.model_dump(), ensure_ascii=False, indent=2)
