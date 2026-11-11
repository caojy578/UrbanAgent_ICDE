# -*- coding: utf-8 -*-
"""统一批量运行器:所有 baseline 共用。

职责:加载查询(支持 --ids/--types/--limit/--skip-dated/--only-dated)、逐条运行某个
BaselineSystem、捕获预算/框架异常转成终止原因、组装结果 JSON、断点续跑(framework_error
按手册 §6.4 可重跑并计数)、导出工具清单、存档 system prompt。

与 UrbanAgent 的 batch.py / react_baseline.py 行为一致,只是 system 可插拔。
"""
import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List

from . import config
from .budget import Budget, Usage, BudgetExceeded, ContextOverflow
from .result import build_result, now_iso

TYPES = ("FR", "CR", "SD", "CC", "AI")


def _load_queries(path: str) -> List[Dict[str, Any]]:
    items = json.load(open(path, "r", encoding="utf-8"))
    if isinstance(items, dict):
        items = items["queries"]
    return items


def _filter(items, args):
    if args.ids:
        wanted = {x.strip() for x in args.ids.split(",") if x.strip()}
        items = [q for q in items if q["id"] in wanted]
    if args.types:
        pref = tuple(x.strip().upper() for x in args.types.split(","))
        items = [q for q in items if q["id"].upper().startswith(pref)]
    if args.skip_dated or args.only_dated:
        tm = json.load(open(args.skip_dated or args.only_dated, "r", encoding="utf-8"))
        dated = set(tm.keys()) if isinstance(tm, dict) else {x["id"] for x in tm}
        items = [q for q in items if (q["id"] not in dated) == bool(args.skip_dated)]
    if args.limit:
        items = items[:args.limit]
    return items


def run_batch(system, argv=None) -> int:
    """跑一个 BaselineSystem。返回退出码(0 = 无框架错误)。"""
    ap = argparse.ArgumentParser(prog="run %s" % system.name)
    ap.add_argument("--queries", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mcp", required=True)
    ap.add_argument("--ids", default=None)
    ap.add_argument("--types", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--skip-dated", default=None)
    ap.add_argument("--only-dated", default=None)
    ap.add_argument("--allow-missing-servers", action="store_true")
    args = ap.parse_args(argv)

    items = _filter(_load_queries(args.queries), args)
    if not items:
        print("no queries selected", file=sys.stderr)
        return 2

    # ---- 连接工具池(direct_llm 不挂工具)----
    from .mcp_pool import MCPPool
    pool = None
    if system.uses_tools:
        pool = MCPPool(args.mcp, exclude=config.EXCLUDE_SERVERS,
                       qps_max_retry=config.QPS_MAX_RETRY)
        if pool.failures:
            for s, why in pool.failures.items():
                print("[MCP] %s FAILED: %s" % (s, why), file=sys.stderr)
            if not args.allow_missing_servers:
                pool.close()
                return 3
        os.makedirs(args.out, exist_ok=True)
        json.dump(pool.manifest(), open(os.path.join(args.out, "tools_manifest.json"),
                                        "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("[MCP] %d tools from %d servers" % (len(pool.tool_names()), 6 - len(pool.failures)))

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "system_prompt.txt"), "w", encoding="utf-8") as fh:
        fh.write(system.system_prompt(pool))          # environment.md 存档用
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
            if os.path.exists(out_path):                       # 断点续跑
                prev = json.load(open(out_path, "r", encoding="utf-8"))
                if prev.get("termination_reason") != "framework_error":
                    skipped += 1
                    continue
                prev_rerun = int(prev.get("infra_rerun_count") or 0) + 1

            print("[%d/%d] %s %s" % (i, len(items), item["id"],
                                     item["query"][:50].replace("\n", " ")))
            result = _run_one(system, item, pool, prev_rerun, raw_log_dir)
            tmp = out_path + ".tmp"
            json.dump(result, open(tmp, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2, default=str)
            os.replace(tmp, out_path)

            done += 1
            if result["termination_reason"] == "framework_error":
                failed += 1
                print("    !! framework_error: %s" % result["notes"], file=sys.stderr)
            else:
                print("    -> %s | llm_calls=%s tokens=%s tools=%d | %.1fs" % (
                    result["termination_reason"], result["llm_calls"],
                    result["usage"]["total_tokens"], len(result["tool_calls"]),
                    result["latency_seconds"]))
            time.sleep(config.SLEEP_BETWEEN_QUERIES)
    finally:
        if pool is not None:
            pool.close()

    print("finished: %d run, %d skipped, %d framework errors" % (done, skipped, failed))
    return 0 if failed == 0 else 1


def _run_one(system, item, pool, prev_rerun, raw_log_dir) -> Dict[str, Any]:
    budget = Budget(config.MAX_LLM_CALLS, config.MAX_SECONDS)
    usage = Usage()
    if pool is not None:
        pool.reset_trace()
    start_iso = now_iso()
    t0 = time.time()
    notes = ""
    try:
        outcome = system.run(item["query"], pool, budget, usage)
    except BudgetExceeded as err:
        outcome = _outcome(None, False, err.reason)          # step_limit | timeout
    except ContextOverflow as err:                           # 模型行为失败,判失败不重跑
        outcome = _outcome(None, False, "context_overflow",
                           "ContextOverflow: %s" % (err.detail or "")[:300])
    except Exception as err:                                 # noqa: BLE001 — infra 故障
        # 防御:LangChain 路径下,context 撑爆常经 relay 浮现成 503「输入过长」而非干净的
        # ContextOverflow。若异常带「输入过长/context」信号且该次确有超大 tool 返回(>800k 字符),
        # 判 context_overflow(模型行为失败、不重跑),与 native_tool 的 SD-24 口径一致;
        # 否则才是真 infra 抽风,记 framework_error 等待 resume 重跑。
        s = str(err).lower()
        ctx_sig = ("输入过长" in str(err) or "context_length" in s
                   or "maximum context" in s or "too long" in s
                   or "503" in s or "remoteprotocol" in s or "incomplete" in s
                   or "context overflow" in s or "撑爆" in str(err))
        big_tool = pool is not None and any(
            len(c.get("raw_result") if isinstance(c.get("raw_result"), str)
                else str(c.get("raw_result") or "")) > 800_000
            for c in (pool.trace() or []))
        if ctx_sig and big_tool:
            outcome = _outcome(None, False, "context_overflow",
                               "503/输入过长 + 超大工具返回: %s" % str(err)[:200])
        else:
            outcome = _outcome(None, False, "framework_error",
                               "%s: %s" % (type(err).__name__, str(err)[:300]))
    latency = time.time() - t0
    tool_calls = pool.trace() if pool is not None else []
    return build_result(
        item, system.name, system.framework_version, config.TEMPERATURE,
        usage.model_id or config.MODEL, start_iso, now_iso(), latency,
        budget, usage, tool_calls, outcome.final_answer, outcome.asked_clarification,
        outcome.termination_reason, outcome.notes, prev_rerun)


def _outcome(ans, clar, term, notes=""):
    from systems.base import Outcome
    return Outcome(ans, clar, term, notes)
