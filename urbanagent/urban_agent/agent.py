# -*- coding: utf-8 -*-
"""UrbanAgent: single-agent tool-calling workflow.

Reported pipeline:

    Q --f_cog--> U --[reason <-> invoke/observe]--> (O, R_hat)
      --f_syn--> R

One LLM policy performs cognition, adaptive tool use, and evidence-aligned
finalization. Runtime guards record every tool call, reject unusable
observations, prevent redundant successful calls, and enforce the query budget.
The legacy DAG path remains available through URBAN_AGENT_CORE=dag but is not
the configuration reported in the paper.
"""
import json
import os
import time
import uuid
from typing import Any, Dict, Optional

from .config import config
from .llm import LLM, BudgetExceeded
from .tools import ToolRegistry, build_default_registry
from .workflow import (Solution, constraint_note, execute_graph, run_cognition,
                       run_planning, run_react, run_replanning, run_synthesis,
                       run_synthesis_react, skipped_task)


class UrbanAgent:
    def __init__(self, llm: Optional[LLM] = None,
                 registry: Optional[ToolRegistry] = None):
        self.llm = llm or LLM()
        self.registry = registry or build_default_registry()

    # ------------------------------------------------------------------
    def run(self, query: str, clarify: bool = True,
            trace_path: Optional[str] = None,
            max_llm_calls: Optional[int] = None,
            timeout_s: Optional[float] = None) -> Solution:
        trace: Dict[str, Any] = {"id": uuid.uuid4().hex[:12], "query": query,
                                 "model": self.llm.model, "stages": {},
                                 "termination_reason": "normal",
                                 "ablation": {
                                     "core": config.core,
                                     "skip_cognition": bool(config.skip_cognition),
                                     "obs_recovery": bool(config.obs_recovery),
                                     "invoke_mode": config.invoke_mode,
                                     "syn": config.react_synthesis,
                                 }}
        # per-query budget (parity with the baseline manual: <=25 calls / 10 min)
        budget_calls = config.max_llm_calls_per_query if max_llm_calls is None else max_llm_calls
        budget_time = config.query_timeout_s if timeout_s is None else timeout_s
        self.llm.max_calls = (self.llm.usage["calls"] + budget_calls) if budget_calls else None
        self.llm.deadline = (time.time() + budget_time) if budget_time else None
        t0 = time.time()
        try:
            solution = self._pipeline(query, clarify, trace)
        except BudgetExceeded as err:
            trace["termination_reason"] = err.reason
            solution = Solution(
                status="failed",
                answer="Budget exhausted (%s) before the workflow completed." % err.reason)
            trace["stages"]["solution"] = solution.model_dump()
        except Exception as err:  # noqa: BLE001 — record, then re-raise
            trace["error"] = repr(err)
            trace["termination_reason"] = "framework_error"
            raise
        finally:
            trace["latency_s"] = round(time.time() - t0, 2)
            trace["usage"] = dict(self.llm.usage)
            trace["model_id"] = getattr(self.llm, "model_id", None) or self.llm.model
            self._dump(trace, trace_path)
        return solution

    # ------------------------------------------------------------------
    def _pipeline(self, query: str, clarify: bool, trace: Dict[str, Any]) -> Solution:
        # Stage 1: cognition  Q -> U  (skipped in the w/o Cognition ablation)
        if config.skip_cognition:
            task = skipped_task(query)
            trace["stages"]["cognition"] = {"skipped": True, **task.model_dump()}
        else:
            task = run_cognition(self.llm, query)
            trace["stages"]["cognition"] = task.model_dump()

        # Missing information is an execution precondition: expose it before
        # invocation instead of silently inferring parameters (L3 behaviour).
        if (not config.skip_cognition and clarify
                and task.clarification_needed and task.missing_info):
            questions = " ".join(m.question for m in task.missing_info)
            solution = Solution(status="clarification", clarification=questions,
                                answer="Clarification needed before execution: %s" % questions)
            trace["stages"]["solution"] = solution.model_dump()
            return solution

        # ReAct-core backbone (v2, default): a single adaptive reason-act-observe
        # loop over the full toolset replaces the rigid plan-then-execute DAG. The
        # urban modules (cognition/clarification above, tool grounding inside the
        # loop, evidence-aligned finalization below) are layered on this backbone.
        if config.core == "react":
            observations: Dict[str, Any] = {}
            final_text = ""
            transcript: list = []
            try:
                _, final_text = run_react(
                    self.llm, task, self.registry, query, observations,
                    transcript=transcript)
                answer = final_text
                trace["stages"]["react_draft"] = final_text  # pre-synthesis draft (audit)
                if config.react_synthesis == "rewrite" and final_text:
                    # Finalization stage: rewrite the loop's draft into a committed
                    # answer (kills trailing offers / no-commit, pulls finest fact).
                    answer = run_synthesis_react(self.llm, task, observations, final_text)
                elif config.react_synthesis != "off" and final_text:
                    answer = final_text + constraint_note(self.llm, task, observations, final_text)
            except BudgetExceeded as err:
                # Keep every tool observation gathered so far (process metrics),
                # answer with whatever the loop committed before the budget ran out.
                trace["termination_reason"] = err.reason
                answer = final_text
            failed = not (answer or "").strip()
            solution = Solution(answer=(answer or "").strip(),
                                status="failed" if failed else "ok")
            trace["stages"]["react_messages"] = list(transcript)
            trace["stages"]["execution"] = {k: v.model_dump() for k, v in observations.items()}
            trace["replan_rounds"] = 0
            trace["stages"]["solution"] = solution.model_dump()
            return solution

        # Stage 2: planning  U -> G
        graph = run_planning(self.llm, task, self.registry)
        trace["stages"]["planning"] = graph.model_dump()
        observations: Dict[str, Any] = {}
        solution = None
        replan_rounds = 0

        # Ablation "ReAct → DAG": one frozen plan, no added nodes, shared rewrite.
        if config.core == "static_dag":
            try:
                execute_graph(self.llm, task, graph, self.registry, observations)
            except BudgetExceeded as err:
                trace["termination_reason"] = err.reason
            draft = _draft_from_observations(observations)
            trace["stages"]["react_draft"] = draft
            answer = draft
            if config.react_synthesis == "rewrite" and draft:
                answer = run_synthesis_react(self.llm, task, observations, draft)
            elif config.react_synthesis != "off" and draft:
                answer = draft + constraint_note(self.llm, task, observations, draft)
            failed = not (answer or "").strip()
            solution = Solution(answer=(answer or "").strip(),
                                status="failed" if failed else "ok")
            trace["stages"]["execution"] = {k: v.model_dump() for k, v in observations.items()}
            trace["replan_rounds"] = 0
            trace["stages"]["solution"] = solution.model_dump()
            return solution

        # Legacy DAG backbone (URBAN_AGENT_CORE=dag): execute + DAG synthesis + replan.
        try:
            for rnd in range(config.max_replan_rounds + 1):
                execute_graph(self.llm, task, graph, self.registry, observations)
                solution = run_synthesis(self.llm, task, observations)
                if rnd == config.max_replan_rounds:
                    break
                add = run_replanning(self.llm, task, observations, self.registry)
                if not add.nodes:
                    break
                graph.nodes.extend(add.nodes)
                replan_rounds += 1
        except BudgetExceeded:
            if solution is None:
                raise
        finally:
            trace["stages"]["planning"] = graph.model_dump()
            trace["stages"]["execution"] = {k: v.model_dump() for k, v in observations.items()}
            trace["replan_rounds"] = replan_rounds

        trace["stages"]["solution"] = solution.model_dump()
        return solution

    # ------------------------------------------------------------------
    @staticmethod
    def _dump(trace: Dict[str, Any], trace_path: Optional[str]) -> None:
        path = trace_path
        if path is None:
            os.makedirs(config.trace_dir, exist_ok=True)
            path = os.path.join(config.trace_dir, "%s.json" % trace["id"])
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(trace, fh, ensure_ascii=False, indent=2, default=str)
        except OSError:
            pass


def _draft_from_observations(observations: Dict[str, Any]) -> str:
    """Controller-neutral draft for static DAG: summaries only, no extra LLM."""
    parts = []
    for ob in observations.values():
        summary = getattr(ob, "summary", "") or ""
        if summary:
            parts.append("[%s] %s" % (getattr(ob, "node_id", ""), summary))
    return "\n".join(parts).strip()
