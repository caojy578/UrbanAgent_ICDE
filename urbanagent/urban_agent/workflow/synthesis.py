# -*- coding: utf-8 -*-
"""Synthesis utilities for the reported ReAct path and legacy DAG path.

The reported path calls ``run_synthesis_react`` to rewrite the ReAct draft
against the structured task and recorded observations. The older
``run_synthesis`` and ``constraint_note`` entry points retain deterministic
candidate checks for compatibility experiments; they are not used by the
paper's reported configuration.
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from ..llm import LLM
from .cognition import format_task
from .schemas import (Candidate, HardConstraint, Observation, Solution,
                      StructuredTask)

_SYSTEM = """\
You are the synthesis module of an urban life agent. You receive the
structured task U and the observation set O collected by tool execution.

1. Extract every candidate solution supported by the observations (a POI, a
   route option, a computed figure, a factual finding...).
2. For each hard-constraint attribute, fill the candidate's measured value
   from the observations (numbers as numbers; omit attributes with no
   evidence rather than guessing).
3. Draft a final answer grounded in the observations, and COMMIT to the best-
   supported answer. If the observations contain a usable value for what the
   query asks — a coordinate, a POI, a rating, a number, an address, a route —
   STATE it directly and completely: give the concrete facts the query
   requested (coordinates as explicit lon,lat numbers; the place's name; the
   computed figure; the full address). Do NOT withhold or hedge a usable answer
   merely because a POI's name is not an exact string match (pick the closest
   matching POI and name it), because several candidates exist (choose the best
   and say why), or because one detail is imperfect (report the best available
   result and note the caveat in one clause). Only state that a fact is genuinely
   missing when NO observation provides it — never invent data, but never bury a
   real answer under caveats either.
4. Write answer_draft in the SAME language as the user's query (a Chinese
   query gets a Chinese answer); keep proper nouns as reported by the tools.

Return ONLY a JSON object:
{
  "candidates": [
    {"name": "...",
     "attributes": {"<hard-constraint attribute or metric>": <value>},
     "evidence": "<which observation supports it>"}
  ],
  "answer_draft": "<final answer text, cite concrete numbers>"
}
For purely factual queries a single candidate carrying the fact is fine.
"""

_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _as_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = _NUM.search(value.replace(",", ""))
        if m:
            return float(m.group())
    return None


def verify_hard(candidate: Candidate,
                constraints: List[HardConstraint]) -> Tuple[bool, List[str]]:
    """V(R, C_hard): deterministic boundary check. Unmeasured attributes are
    skipped (cannot be verified), measured violations prune the candidate."""
    violated: List[str] = []
    for c in constraints:
        if c.attribute not in candidate.attributes:
            continue
        actual = _as_number(candidate.attributes[c.attribute])
        expected = c.value
        ok = True
        if c.operator == "between" and isinstance(expected, (list, tuple)) and len(expected) == 2:
            lo, hi = _as_number(expected[0]), _as_number(expected[1])
            ok = actual is not None and lo is not None and hi is not None and lo <= actual <= hi
        elif c.operator in ("<=", "within"):
            e = _as_number(expected)
            ok = actual is not None and e is not None and actual <= e
        elif c.operator == ">=":
            e = _as_number(expected)
            ok = actual is not None and e is not None and actual >= e
        elif c.operator == "<":
            e = _as_number(expected)
            ok = actual is not None and e is not None and actual < e
        elif c.operator == ">":
            e = _as_number(expected)
            ok = actual is not None and e is not None and actual > e
        elif c.operator == "==":
            if actual is not None and _as_number(expected) is not None:
                ok = actual == _as_number(expected)
            else:
                a = str(candidate.attributes[c.attribute]).strip().lower()
                e = str(expected).strip().lower()
                # Place/name equality: accept containment either way so an admin
                # suffix does not read as a violation (银川市 ⊇ 银川; 宁夏回族自治区
                # ⊇ 宁夏; 川菜馆 ⊇ 川菜). Avoids spurious constraint-note alarms.
                ok = a == e or (bool(a) and bool(e) and (a in e or e in a))
        if not ok:
            violated.append("%s %s %s (actual: %s)" %
                            (c.attribute, c.operator, expected,
                             candidate.attributes[c.attribute]))
    return (not violated), violated


def score_soft(candidate: Candidate, task: StructuredTask,
               peers: List[Candidate]) -> float:
    """Soft constraints as weighted normalized objectives (max-min scaling)."""
    if not task.soft_constraints:
        return 0.0
    score = 0.0
    for sc in task.soft_constraints:
        values = [(_as_number(p.attributes.get(sc.objective))) for p in peers]
        values = [v for v in values if v is not None]
        mine = _as_number(candidate.attributes.get(sc.objective))
        if mine is None or not values:
            continue
        lo, hi = min(values), max(values)
        norm = 0.5 if hi == lo else (mine - lo) / (hi - lo)
        if sc.direction == "min":
            norm = 1.0 - norm
        score += sc.weight * norm
    return round(score, 4)


_NOTE_SYSTEM = """\
You are the constraint-verification module. You are given the structured task U
(with its hard constraints) and the observation set O gathered by tool calls,
plus the agent's committed final answer. Extract the concrete answer
candidate(s) the final answer actually chose, and for each hard-constraint
attribute fill its MEASURED value from the observations (numbers as numbers;
omit an attribute if no observation provides a value — never guess).

Return ONLY: {"candidates":[{"name":"...","attributes":{"<attr>":<value>},
"evidence":"<obs>"}]}. For a purely factual answer a single candidate is fine.
Do NOT rewrite or second-guess the answer; only surface typed values for checking.
"""


def constraint_note(llm: LLM, task: StructuredTask,
                    observations: Dict[str, Observation], final_answer: str) -> str:
    """Deterministic hard-constraint verification for the ReAct-core pipeline.

    Runs V(R, C_hard) over candidates extracted from the committed answer and
    returns ONLY a transparency note (empty string if nothing is flagged). Unlike
    run_synthesis it does NOT re-generate the answer — the ReAct loop's committed
    answer stands; this just annotates any measured hard-constraint violation,
    preserving the paper's "errors inside a success shell" transparency."""
    if not task.hard_constraints:
        return ""
    def _cap(v, n=3000):
        s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
        return s if len(s) <= n else s[:n] + "…[truncated]"
    obs_dump = json.dumps(
        [{"node": ob.node_id, "status": ob.status, "summary": ob.summary,
          "data": _cap(ob.data)} for ob in observations.values() if ob.node_id != "answer"],
        ensure_ascii=False, default=str)
    try:
        payload = llm.chat_json(
            _NOTE_SYSTEM, "Structured task U:\n%s\n\nObservation set O:\n%s\n\n"
            "Agent's committed final answer:\n%s" % (format_task(task), obs_dump, final_answer))
    except Exception:  # noqa: BLE001 — annotation is best-effort, never fatal
        return ""
    if isinstance(payload, list):
        payload = {"candidates": [c for c in payload if isinstance(c, dict)]}
    try:
        cands = [Candidate.model_validate(c) for c in payload.get("candidates", [])]
    except Exception:  # noqa: BLE001
        return ""
    flagged = []
    for c in cands:
        ok, violated = verify_hard(c, task.hard_constraints)
        if not ok:
            flagged.append("%s (%s)" % (c.name, ", ".join(violated)))
    if not flagged:
        return ""
    return ("\n\n[约束核验] 以下 %d 项经核验可能未完全满足某项硬约束,供参考:%s"
            % (len(flagged), "; ".join(flagged)))


_REACT_SYNTH_SYSTEM = """\
You are the ANSWER-FINALIZATION module of an urban-life agent. You are given the
user's structured task U, the observation set O (the raw results the tool calls
returned), and the agent's DRAFT answer produced while reasoning. Your job is to
rewrite the draft into the FINAL committed answer shown to the user.

HARD RULES:
1. COMMIT. State the conclusion directly. If U asks for a concrete deliverable
   (an address, coordinate, price, rating, hours, a ranked list, a yes/no) and O
   contains what is needed, GIVE it as a settled answer. Never present candidates
   and then ask the user to pick; decide, using U's own criteria, and say which.
2. NO TRAILING OFFER — BUT KEEP A GENUINE CLARIFICATION.
   (a) Never end by offering to do work the tools could already have done and that
       U already asked for (no "要我继续扩展搜索吗 / 需要我帮你查收费吗 / 要不要我列更多 /
       下一步"). If such a detail is merely missing from O, state that in ONE plain
       sentence — do not turn it into a question. In particular, when something the
       query asked for is UNREACHABLE by the available tools (e.g. a specific past
       date's weather the forecast tool cannot cover, a coordinate a provider does
       not serve), state that limitation as a settled FACT ("2026-07-13 09:00 的历史
       天气无法由当前天气工具获取") — do NOT offer to try another data source ("要我用
       NOAA/其它源查吗"). Offering an out-of-reach alternative is still a trailing
       offer; close the item with the fact and move on.
   (b) HOWEVER, if U is genuinely ambiguous/under-specified and cannot be answered
       without information ONLY THE USER can supply — travel/stay dates, personal
       budget, a subjective preference, or which of several distinct targets/areas
       they mean — and the draft asks for exactly that, PRESERVE that clarifying
       question verbatim in substance. Asking for irreducibly user-specific input
       is correct, not a trailing offer. When in doubt whether the draft's question
       is (a) or (b), KEEP it.
3. USE THE FINEST EVIDENCE IN O. If a primary tool returned a coarse result
   (e.g. reverse-geocode only to district level) but another observation (nearby
   POIs / around-search / detail) contains the finer fact (street, 门牌, landmark
   name), COMMIT to that finer fact instead of complaining about the coarse one.
4. GROUNDED ONLY. Use only facts present in O or the draft. Do NOT invent
   numbers, names, coordinates, or ratings. Report coordinates exactly as O gives
   them (amap = GCJ-02; no conversion).
5. If U asks for items "above average / higher-rated", and O lets you establish
   that (an average, or a clear threshold), state the comparison; otherwise state
   the ratings you found and that they are the highest available in O — do not
   leave it as an open question.
6. Keep it clean and well-organized. Drop meta-chatter, hedging, and process
   narration. Answer in the user's language.

Output ONLY the final answer text — no JSON, no preamble, no "Final answer:".
"""


def run_synthesis_react(llm: LLM, task: StructuredTask,
                        observations: Dict[str, Observation],
                        draft_answer: str) -> str:
    """Rewrite the ReAct loop's draft into a committed final answer.

    Unlike constraint_note (which only appends a verification remark), this takes
    the whole observation set + draft and produces the answer that is actually
    returned — forcing commitment, killing trailing offers, and pulling the
    finest available fact out of O. Best-effort: on any failure the original
    draft is returned unchanged so the pipeline never regresses to empty."""
    def _cap(v, n=3500):
        s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
        return s if len(s) <= n else s[:n] + "…[truncated]"
    obs_dump = json.dumps(
        [{"node": ob.node_id, "status": ob.status, "summary": ob.summary,
          "data": _cap(ob.data)} for ob in observations.values() if ob.node_id != "answer"],
        ensure_ascii=False, default=str)
    try:
        msg = llm.chat([
            {"role": "system", "content": _REACT_SYNTH_SYSTEM},
            {"role": "user", "content": "Structured task U:\n%s\n\nObservation set O:\n%s\n\n"
             "Agent's draft answer:\n%s" % (format_task(task), obs_dump, draft_answer)},
        ])
        final = (getattr(msg, "content", None) or "").strip()
    except Exception:  # noqa: BLE001 — never fatal; fall back to draft
        return draft_answer
    return final or draft_answer


def run_synthesis(llm: LLM, task: StructuredTask,
                  observations: Dict[str, Observation]) -> Solution:
    # Cap each observation's data INDIVIDUALLY so every tool result reaches the
    # synthesizer. A single global truncation (previously obs_dump[:12000]) would
    # silently drop whichever observations landed after the cut, making synthesis
    # falsely report later tool results (e.g. a transit route) as "missing" even
    # though the tool succeeded — the root cause of dropped multi-tool comparisons.
    def _cap(v, n=3500):
        s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
        return s if len(s) <= n else s[:n] + "…[truncated]"

    obs_dump = json.dumps(
        [{"node": ob.node_id, "status": ob.status,
          "summary": ob.summary, "data": _cap(ob.data)} for ob in observations.values()],
        ensure_ascii=False, default=str)
    payload = llm.chat_json(
        _SYSTEM, "Structured task U:\n%s\n\nObservation set O:\n%s"
        % (format_task(task), obs_dump))
    if isinstance(payload, list):
        # model occasionally emits a bare JSON array (the candidate list)
        payload = {"candidates": [c for c in payload if isinstance(c, dict)]}

    candidates = [Candidate.model_validate(c) for c in payload.get("candidates", [])]

    # Deterministic hard-constraint check — ANNOTATE, do not prune. The typed
    # verdict is recorded per candidate and surfaced as a transparency note, but
    # a violating candidate is NOT discarded: the agent still returns the best
    # available answer (as a baseline would) instead of manufacturing a
    # self-inflicted "no result". Hard pruning previously made ua report failure
    # on tasks it had actually answered — e.g. a 四川菜 place flagged against a
    # literal `cuisine == 川菜` constraint, or a valid answer dropped on a
    # synonym/format mismatch. Exposing the concern keeps the "errors in a
    # success shell" transparency without sacrificing task completion.
    for cand in candidates:
        cand.hard_check, cand.violated = verify_hard(cand, task.hard_constraints)

    # soft-constraint multi-objective ranking over ALL candidates
    for cand in candidates:
        cand.score = score_soft(cand, task, candidates)
    ordered = sorted(candidates, key=lambda c: (c.score or 0.0), reverse=True)

    answer = payload.get("answer_draft", "")
    flagged = [c for c in ordered if c.hard_check is False]
    if flagged:
        note = "; ".join("%s (%s)" % (c.name, ", ".join(c.violated)) for c in flagged)
        answer += ("\n\n[约束核验] 以下 %d 项可能未完全满足某项硬约束,已保留供参考"
                   "(如需严格筛选请自行确认):%s" % (len(flagged), note))

    failed = all(ob.status == "failed" for ob in observations.values()) if observations else True
    return Solution(answer=answer.strip(), candidates=ordered,
                    status="failed" if failed and not candidates else "ok")
