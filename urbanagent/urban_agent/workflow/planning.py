# -*- coding: utf-8 -*-
"""Stage 2 — Planning module: f_plan : U -> G.

Decomposes the structured task into atomic sub-tasks and models the execution
flow as a directed acyclic graph G = (V, E).  A directed edge i->j means the
output of v_i instantiates the arguments of v_j.

Crucially, the planner does NOT engage in unconstrained fictitious planning:
the functional descriptions of the available tool library (Tool Metadata) are
injected into the prompt, so every node's semantic objective is aligned with a
real, executable service interface.  Structural validity (acyclicity, known
dependencies) is checked deterministically in code and one repair round is
attempted on failure.
"""
import json
from typing import List

from ..llm import LLM
from ..tools import ToolRegistry
from .cognition import format_task
from .schemas import StructuredTask, TaskGraph

_SYSTEM = """\
You are the planning module of an urban life agent. Decompose the structured
task into a MINIMAL directed acyclic graph of atomic sub-tasks executable with
the available tools.

Available tools (Tool Metadata):
%s

Return ONLY a JSON object:
{
  "nodes": [
    {"id": "n1",
     "description": "<atomic objective, one tool action worth of work>",
     "tool_candidates": ["<tool name from the list>", "..."],
     "args_template": {"<param>": "<literal value or placeholder like {n1.location}>"},
     "depends_on": []}
  ]
}

Rules:
- Every node must be executable by one of tool_candidates; only use listed
  tools, written as the BARE tool name exactly as listed (e.g. "maps_geo",
  never a server-qualified form like "amap-maps:maps_geo").
- depends_on lists node ids whose OUTPUT is needed to fill this node's arguments;
  use {nodeId.field} placeholders in args_template for such values.
- TOOL APPLICABILITY: judge each tool's coverage from its full metadata —
  server identity, description and parameter semantics. A provider only works
  within its actual coverage (e.g. a China-focused map provider cannot geocode
  or route overseas addresses; a US business platform does not cover Chinese
  merchants). Never assign a node's location to a tool whose provider does not
  cover it — prefer a tool whose metadata fits, and if the query already
  supplies a value (a distance, a coordinate, an address), consume it directly
  instead of planning a tool call to re-derive it. Some queries legitimately
  need NO tool from a given server.
- tool_candidates SHOULD list genuine alternatives (including tools from other
  servers that can achieve the same objective) in preference order, so the
  executor can fall back when the first choice fails.
- Respect data-flow preconditions: if a node's tool REQUIRES an argument the
  query does not supply (e.g. routing tools require start/end coordinates),
  add an upstream node whose OUTPUT actually contains that value, and read it
  via {nodeId.field}. Retrieve candidates before fetching details; check a
  condition (e.g. weather) before the branch that depends on it.
- Observed contract of the amap tools: maps_around_search / maps_text_search
  return POIs WITHOUT coordinates — only id, name, address. Within an amap
  chain, to route to or measure distance to a SELECTED search-result POI you
  MUST first insert a maps_search_detail node (input: that POI's id) and make
  the routing/distance node read the coordinate from it (e.g. {nDetail.location}).
- Parallel branches are simply nodes with disjoint dependencies. depends_on
  encodes DATA dependencies only (a node consumes another node's output);
  narrative ordering words in the request ("然后/先...再") do not by
  themselves create a dependency.
- For conditional queries ("if it rains take metro, else cycle"), include the
  probe node (weather) and BOTH branch nodes so the executor can decide with
  real observations; note the condition in the branch node description.
- A final comparison/decision step that needs no external tool must NOT be a
  node — synthesis handles it. Keep the graph minimal: no redundant calls.
"""


_REPLAN_SYSTEM = """\
You are the adaptive re-planning module of an urban life agent. An initial plan
has already executed; you are given the structured task, the observations
collected so far (with each node's status and data), and must decide whether the
task can now be answered, or whether TARGETED additional tool actions are needed
to fill a gap.

Available tools (Tool Metadata):
%s

Return ONLY a JSON object with the NEW nodes to run now — an EMPTY list if the
observations already support a complete answer:
{"nodes": [ {"id": "r1", "description": "...", "tool_candidates": ["..."],
             "args_template": {"...": "..."}, "depends_on": []} ]}

Rules:
- Output ONLY NEW nodes that obtain still-MISSING information. Do NOT repeat an
  action whose result is already in the observations.
- New node ids MUST be fresh (prefix them with "r", e.g. r1, r2). You MAY depend
  on an EXISTING observation id via {id.field} placeholders and list it in
  depends_on.
- Only use listed tools, bare names. Same applicability rules as planning: a
  China map provider cannot geocode/route overseas; maps_text_search /
  maps_around_search return POIs WITHOUT coordinates, so to route/measure to a
  chosen POI first add a maps_search_detail node and read {nDetail.location};
  resolve relative time to absolute start/end before querying.
- Typical gaps worth fixing: a node FAILED and an alternate tool or corrected
  arguments could succeed; a required value (a coordinate, a rating, a
  time-bounded count, a distance) was never obtained; the plan geocoded the
  WRONG city and a city-scoped maps_text_search is needed; a hard-constraint
  attribute still has no measured value.
- IMPORTANT gap: a threshold filter (rating ≥ X / price ≤ Y) concluded "no
  candidate qualifies" but NOT every candidate returned by the earlier search
  was actually detail-checked — add maps_search_detail nodes for the still-
  unchecked candidate ids from that search result before accepting "none found".
- If the observations already let synthesis answer the task fully, return
  {"nodes": []}. Keep it MINIMAL — only nodes truly needed.
- Do NOT re-plan for a gap that no tool can close: if the task is blocked on
  USER-SPECIFIC or under-specified information that must be supplied by the user
  (an ambiguous request, a missing personal location/preference, a choice among
  fundamentally different entities) rather than on a fetchable value, return
  {"nodes": []} — the correct response there is to ask the user, not to gather
  more data.
"""


def run_replanning(llm: LLM, task: StructuredTask, observations, registry: ToolRegistry,
                   repair_rounds: int = 1) -> TaskGraph:
    """Second-and-later planning pass: inspect observations, emit only the NEW
    nodes needed to close remaining gaps (or an empty graph when done)."""
    from .schemas import Observation  # local import avoids a cycle
    existing = set(observations.keys())
    obs_lines = []
    for ob in observations.values():
        data = ob.data
        s = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, default=str)
        if s and len(s) > 900:
            s = s[:900] + "…"
        obs_lines.append("- [%s] status=%s :: %s\n    data: %s"
                         % (ob.node_id, ob.status, ob.summary or "", s))
    system = _REPLAN_SYSTEM % registry.catalog()
    user = ("Structured task U:\n%s\n\nObservations so far:\n%s\n\n"
            "Existing node ids (do NOT reuse): %s\nEmit only fresh nodes to fill "
            "gaps, or {\"nodes\": []} if the task is already answerable."
            % (format_task(task), "\n".join(obs_lines) or "(none)", sorted(existing)))
    payload = llm.chat_json(system, user)
    for _ in range(repair_rounds + 1):
        try:
            graph = TaskGraph.model_validate(payload)
            # keep only genuinely-new nodes; drop any that collide with existing ids
            graph.nodes = [n for n in graph.nodes if n.id not in existing]
            if not graph.nodes:
                return graph
            _validate_replan(graph, registry, existing)
            return graph
        except Exception as err:  # noqa: BLE001
            payload = llm.chat_json(system, user + "\n\nYour previous output was "
                                    "invalid: %s\nReturn corrected JSON." % err)
    return TaskGraph(nodes=[])


def _validate_replan(graph: TaskGraph, registry: ToolRegistry, existing: set) -> None:
    seen = set(existing)
    for node in graph.nodes:
        if node.id in seen:
            raise ValueError("duplicate node id %s" % node.id)
        seen.add(node.id)
        if not node.tool_candidates:
            raise ValueError("node %s has no tool_candidates" % node.id)
        canon, unknown = [], []
        for t in node.tool_candidates:
            c = registry.resolve(t)
            (canon if c else unknown).append(c or t)
        if unknown:
            raise ValueError("node %s references unknown tools: %s" % (node.id, unknown))
        node.tool_candidates[:] = canon
        # dependencies must point to an existing observation or another new node
        for dep in node.depends_on:
            if dep not in seen and dep not in {n.id for n in graph.nodes}:
                raise ValueError("node %s depends on unknown node %s" % (node.id, dep))


def run_planning(llm: LLM, task: StructuredTask, registry: ToolRegistry,
                 repair_rounds: int = 1) -> TaskGraph:
    system = _SYSTEM % registry.catalog()
    user = "Structured task U:\n%s" % format_task(task)
    payload = llm.chat_json(system, user)
    last_err: Exception = RuntimeError("planning failed")
    for _ in range(repair_rounds + 1):
        try:
            graph = TaskGraph.model_validate(payload)
            _validate(graph, registry)
            return graph
        except Exception as err:  # noqa: BLE001 — feed the error back for repair
            last_err = err
            payload = llm.chat_json(
                system,
                user + "\n\nYour previous plan was invalid: %s\n"
                       "Return a corrected JSON plan." % err)
    raise last_err


def _validate(graph: TaskGraph, registry: ToolRegistry) -> None:
    if not graph.nodes:
        raise ValueError("empty plan")
    seen: List[str] = []
    for node in graph.nodes:
        if node.id in seen:
            raise ValueError("duplicate node id %s" % node.id)
        seen.append(node.id)
        if not node.tool_candidates:
            raise ValueError("node %s has no tool_candidates" % node.id)
        # 规范化工具名(连字符/下划线/大小写归一),让执行期能精确匹配注册名;
        # 真正不存在的才报 unknown。
        canon, unknown = [], []
        for t in node.tool_candidates:
            c = registry.resolve(t)
            (canon if c else unknown).append(c or t)
        if unknown:
            raise ValueError("node %s references unknown tools: %s" % (node.id, unknown))
        node.tool_candidates[:] = canon
    graph.topological_order()  # raises on cycles / unknown deps
