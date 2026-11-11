# -*- coding: utf-8 -*-
"""Batch runner: UrbanAgent over the shared 250-query benchmark.

Produces one result file per query in *exactly* the schema of
``baseline_experiments/schema/result_example.json`` (baseline name
``urban_agent``), so `scripts/validate_results.py` and the paper's analysis
pipeline treat our method and the five baselines uniformly.

Manual rules enforced here:
  * only the ``query`` field is fed to the agent (never reference_full_query);
  * a clarification question is a terminal answer (asked_clarification=true);
  * serial execution, one fresh LLM (fresh usage counters) per query;
  * token usage strictly from API usage fields;
  * raw tool returns stored untruncated;
  * per-query budget <= 25 LLM calls / 10 min -> termination_reason.

Usage:
    export OPENAI_API_KEY=...
    python -m urban_agent.batch \
        --queries ../baseline_experiments/queries/runtime/queries_2026-07-05.json \
        --mcp ../mcp.json \
        --out ../baseline_experiments/results/urban_agent
"""
import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import __version__
from .agent import UrbanAgent
from .config import config
from .llm import LLM
from .tools import ToolRegistry, build_default_registry
from .tools.mcp_registry import build_mcp_registry, close_registry, export_manifest

BASELINE_NAME = "urban_agent"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _flatten_tool_calls(trace: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Trace (per-node records) -> the manual's flat, sequenced tool_calls."""
    calls: List[Dict[str, Any]] = []
    execution = trace.get("stages", {}).get("execution", {}) or {}
    seq = 0
    for node_id in execution:                      # dict preserves execution order
        for rec in execution[node_id].get("tool_calls", []):
            seq += 1
            calls.append({
                "seq": seq,
                "server": rec.get("server", "local"),
                "tool": rec.get("tool"),
                "arguments": rec.get("arguments", {}),
                "success": bool(rec.get("success")),
                "raw_result": rec.get("raw_result"),
                "error": rec.get("error"),
                "latency_seconds": rec.get("latency_seconds", 0.0),
                "diag": rec.get("diag"),
            })
    return calls


def _result_skeleton(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "query_id": item["id"],
        "query_type": item.get("type"),
        "level": item.get("level"),
        "query": item["query"],
        "baseline": BASELINE_NAME,
        "model": None,
        "framework_version": "urban_agent==%s" % __version__,
        "temperature": config.temperature,
        "run_timestamp_start": None,
        "run_timestamp_end": None,
        "latency_seconds": None,
        "llm_calls": None,
        "usage": None,
        "tool_calls": [],
        "final_answer": None,
        "asked_clarification": False,
        "termination_reason": "normal",
        "infra_rerun_count": 0,
        "notes": "",
    }


class _HardTimeout(Exception):
    """Raised by the SIGALRM watchdog when a single query overruns the hard
    wall-clock cap — a last-resort backstop for a call that hangs INSIDE a
    blocking LLM/MCP request (where the soft per-query deadline, checked only
    between LLM calls, cannot fire). Keeps one stuck query from stalling the
    whole batch."""


def _alarm_handler(signum, frame):  # noqa: ANN001
    raise _HardTimeout("hard per-query wall-clock timeout")


def run_one(item: Dict[str, Any], registry: ToolRegistry,
            raw_log_dir: str, clarify: bool = True) -> Dict[str, Any]:
    result = _result_skeleton(item)
    llm = LLM()                                   # fresh usage counters per query
    agent = UrbanAgent(llm=llm, registry=registry)
    trace_path = os.path.join(raw_log_dir, "%s.json" % item["id"])

    result["run_timestamp_start"] = _now_iso()
    t0 = time.time()
    # Hard backstop = soft deadline + slack; SIGALRM interrupts blocking syscalls
    # (hung HTTP read, MCP queue wait, thread deadlock) that the soft check misses.
    hard_cap = int(config.query_timeout_s) + 120
    prev_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.alarm(hard_cap)
    try:
        solution = agent.run(item["query"], clarify=clarify, trace_path=trace_path)
    except _HardTimeout as err:
        result["termination_reason"] = "timeout"
        result["notes"] = repr(err)
        solution = None
    except Exception as err:  # noqa: BLE001 — framework bug, not model behaviour
        result["termination_reason"] = "framework_error"
        result["notes"] = repr(err)
        solution = None
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev_handler)
    result["run_timestamp_end"] = _now_iso()
    result["latency_seconds"] = round(time.time() - t0, 2)

    # trace was written by agent.run even on failure — read it back for detail
    trace: Dict[str, Any] = {}
    try:
        with open(trace_path, "r", encoding="utf-8") as fh:
            trace = json.load(fh)
    except (OSError, json.JSONDecodeError):
        pass

    result["model"] = trace.get("model_id") or llm.model
    result["llm_calls"] = llm.usage["calls"]
    result["usage"] = {
        "prompt_tokens": llm.usage["prompt_tokens"],
        "completion_tokens": llm.usage["completion_tokens"],
        "total_tokens": llm.usage["prompt_tokens"] + llm.usage["completion_tokens"],
    }
    result["tool_calls"] = _flatten_tool_calls(trace)
    result["replan_rounds"] = trace.get("replan_rounds", 0)
    if result["termination_reason"] == "normal":
        result["termination_reason"] = trace.get("termination_reason", "normal")

    stages = trace.get("stages") or {}
    result["ablation"] = trace.get("ablation")
    result["cognition"] = stages.get("cognition")
    result["react_draft"] = stages.get("react_draft")
    result["planning"] = stages.get("planning")
    result["trace_id"] = trace.get("id")
    result["trace_path"] = trace_path
    execution = stages.get("execution") or {}
    result["observation_status"] = {
        nid: (ob or {}).get("status")
        for nid, ob in execution.items()
        if nid != "answer"
    }

    if solution is not None:
        result["final_answer"] = solution.clarification or solution.answer
        result["asked_clarification"] = solution.status == "clarification"
    return result


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="urban_agent.batch",
        description="Run UrbanAgent over the shared benchmark queries.")
    parser.add_argument("--queries", required=True,
                        help="runtime queries json (from instantiate_dates.py)")
    parser.add_argument("--out", required=True,
                        help="output root, e.g. .../results/urban_agent")
    parser.add_argument("--mcp", default=config.mcp_config or None,
                        help="mcp.json with the shared toolset (default: "
                             "$URBAN_AGENT_MCP_CONFIG; omit to use built-in local tools)")
    parser.add_argument("--ids", default=None,
                        help="comma-separated query ids to run (e.g. pilot set)")
    parser.add_argument("--types", default=None,
                        help="comma-separated type prefixes to run, e.g. FR,CR")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--skip-dated", default=None,
                        help="path to queries/time_map.json; skip the date-bearing "
                             "queries listed there (they must run same-day as the "
                             "baselines, per manual 5.6)")
    parser.add_argument("--only-dated", default=None,
                        help="path to queries/time_map.json; run ONLY the date-bearing "
                             "queries (for the coordinated same-day run)")
    parser.add_argument("--allow-missing-servers", action="store_true",
                        help="continue even if some MCP servers fail to connect "
                             "(NOT allowed for official runs)")
    parser.add_argument("--no-clarify", action="store_true",
                        help="disable the cognition clarification gate (ablation: "
                             "L3 queries execute with inferred params instead of "
                             "asking the user)")
    args = parser.parse_args(argv)

    with open(args.queries, "r", encoding="utf-8") as fh:
        items = json.load(fh)
    if isinstance(items, dict):          # runtime files wrap the list: {"meta": ..., "queries": [...]}
        items = items["queries"]
    if args.ids:
        wanted = {x.strip() for x in args.ids.split(",") if x.strip()}
        items = [q for q in items if q["id"] in wanted]
    if args.types:
        prefixes = tuple(x.strip().upper() for x in args.types.split(","))
        items = [q for q in items if q["id"].upper().startswith(prefixes)]
    if args.skip_dated or args.only_dated:
        tm_path = args.skip_dated or args.only_dated
        with open(tm_path, "r", encoding="utf-8") as fh:
            tm = json.load(fh)
        dated = set(tm.keys()) if isinstance(tm, dict) else {x["id"] for x in tm}
        if args.skip_dated:
            items = [q for q in items if q["id"] not in dated]
        else:
            items = [q for q in items if q["id"] in dated]
    if args.limit:
        items = items[:args.limit]
    if not items:
        print("no queries selected", file=sys.stderr)
        return 2

    # ---- tool surface --------------------------------------------------
    if args.mcp:
        registry, failures = build_mcp_registry(args.mcp)
        if failures:
            for name, why in failures.items():
                print("[MCP] server %s unavailable: %s" % (name, why), file=sys.stderr)
            if not args.allow_missing_servers:
                print("aborting: official runs need all shared servers up "
                      "(--allow-missing-servers to override for debugging)",
                      file=sys.stderr)
                close_registry(registry)
                return 3
        manifest_path = os.path.join(args.out, "tools_manifest.json")
        os.makedirs(args.out, exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(export_manifest(registry), fh, ensure_ascii=False, indent=2)
        print("[MCP] %d tools from %d servers; manifest -> %s"
              % (len(registry.names()), len(getattr(registry, "mcp_servers", {})),
                 manifest_path))
    else:
        registry = build_default_registry()
        print("[tools] WARNING: using built-in local tools, NOT the shared MCP "
              "surface — debugging only, not comparable with baselines",
              file=sys.stderr)

    raw_log_dir = os.path.join(args.out, "_raw_logs")
    os.makedirs(raw_log_dir, exist_ok=True)

    done = skipped = failed = 0
    try:
        for i, item in enumerate(items, 1):
            prefix = item["id"].split("-")[0]
            out_dir = os.path.join(args.out, prefix)
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, "%s.json" % item["id"])
            prev_rerun = 0
            if os.path.exists(out_path):
                # resume: never overwrite — except framework_error (infra
                # failure), which the manual allows to rerun with a count.
                with open(out_path, "r", encoding="utf-8") as fh:
                    prev = json.load(fh)
                if prev.get("termination_reason") != "framework_error":
                    skipped += 1
                    continue
                prev_rerun = int(prev.get("infra_rerun_count") or 0) + 1

            print("[%d/%d] %s %s" % (i, len(items), item["id"],
                                     item["query"][:50].replace("\n", " ")))
            result = run_one(item, registry, raw_log_dir, clarify=not args.no_clarify)
            result["infra_rerun_count"] = prev_rerun
            tmp = out_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(result, fh, ensure_ascii=False, indent=2, default=str)
            os.replace(tmp, out_path)

            done += 1
            if result["termination_reason"] == "framework_error":
                failed += 1
                print("    !! framework_error: %s" % result["notes"], file=sys.stderr)
            else:
                print("    -> %s | llm_calls=%s tokens=%s tools=%d | %.1fs"
                      % (result["termination_reason"], result["llm_calls"],
                         result["usage"]["total_tokens"], len(result["tool_calls"]),
                         result["latency_seconds"]))
    finally:
        close_registry(registry)

    print("finished: %d run, %d skipped (already done), %d framework errors"
          % (done, skipped, failed))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
