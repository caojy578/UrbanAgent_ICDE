# -*- coding: utf-8 -*-
"""Data structures shared by the four workflow stages.

Naming follows the paper's formalization. ``G`` is used only by the retained
legacy DAG path:
  Q  user query                         -> str
  U  structured task <I, E, C>          -> StructuredTask
  G  task dependency DAG (V, E)         -> TaskGraph
  O  observation set {o_1..o_n}         -> Dict[node_id, Observation]
  R  ranked decision solutions          -> Solution
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- cognition
class HardConstraint(BaseModel):
    """Machine-checkable boundary, e.g. dist <= 3km, price in [300, 600]."""
    attribute: str = Field(description="e.g. distance_km, price, rating, time")
    operator: str = Field(description="one of <=, >=, <, >, ==, between, within")
    value: Any = None
    unit: Optional[str] = None
    description: str = ""


class SoftConstraint(BaseModel):
    """Preference converted into a ranking objective, e.g. 'cheaper is better'."""
    objective: str
    direction: str = Field(default="max", description="max or min")
    weight: float = 1.0


class MissingInfo(BaseModel):
    parameter: str
    question: str


class StructuredTask(BaseModel):
    """U = <I, E, C_hard ∪ C_soft> plus missing-information diagnosis."""
    intent: str = ""
    entities: List[Dict[str, str]] = Field(default_factory=list)
    hard_constraints: List[HardConstraint] = Field(default_factory=list)
    soft_constraints: List[SoftConstraint] = Field(default_factory=list)
    missing_info: List[MissingInfo] = Field(default_factory=list)
    clarification_needed: bool = False


# ---------------------------------------------------------------- planning
class TaskNode(BaseModel):
    """v_i = <desc_i, args_i>: semantic objective + parameter template."""
    id: str
    description: str
    tool_candidates: List[str] = Field(default_factory=list)
    args_template: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)


class TaskGraph(BaseModel):
    """G = (V, E) with edges implied by TaskNode.depends_on."""
    nodes: List[TaskNode] = Field(default_factory=list)

    def topological_order(self) -> List[TaskNode]:
        by_id = {n.id: n for n in self.nodes}
        indeg = {n.id: 0 for n in self.nodes}
        for n in self.nodes:
            for dep in n.depends_on:
                if dep not in by_id:
                    raise ValueError("node %s depends on unknown node %s" % (n.id, dep))
                indeg[n.id] += 1
        order: List[TaskNode] = []
        ready = [n for n in self.nodes if indeg[n.id] == 0]
        while ready:
            node = ready.pop(0)
            order.append(node)
            for m in self.nodes:
                if node.id in m.depends_on:
                    indeg[m.id] -= 1
                    if indeg[m.id] == 0:
                        ready.append(m)
        if len(order) != len(self.nodes):
            raise ValueError("task graph contains a cycle")
        return order


# ---------------------------------------------------------------- execution
class ToolCallRecord(BaseModel):
    tool: str
    server: str = "local"                 # origin MCP server of the tool
    arguments: Dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    result_preview: str = ""
    raw_result: Any = None                # full untruncated tool return (manual rule)
    error: Optional[str] = None
    attempt: int = 1
    latency_seconds: float = 0.0
    # Ablation diagnostics (schema / parse failures). Ignored by TSR flatten.
    diag: Optional[str] = None


class Observation(BaseModel):
    """o_i: what node v_i learned from the physical world."""
    node_id: str
    summary: str = ""
    data: Any = None
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    status: str = "ok"          # ok | failed


# ---------------------------------------------------------------- synthesis
class Candidate(BaseModel):
    name: str
    attributes: Dict[str, Any] = Field(default_factory=dict)
    evidence: str = ""
    hard_check: Optional[bool] = None
    violated: List[str] = Field(default_factory=list)
    score: Optional[float] = None


class Solution(BaseModel):
    """R: final response, with legacy candidate fields when applicable."""
    answer: str = ""
    candidates: List[Candidate] = Field(default_factory=list)
    clarification: Optional[str] = None      # set when execution was withheld
    status: str = "ok"                       # ok | clarification | failed
