# -*- coding: utf-8 -*-
"""统一入口:python run.py --system react --queries ... --mcp ... --out ...

  --system  ∈ {direct_llm, native_tool, react, plan_execute, autogen}
其余参数(--queries/--out/--mcp/--ids/--types/--limit/--skip-dated/--only-dated)
透传给 harness.runner。跑法与 UrbanAgent 一致。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness.runner import run_batch   # noqa: E402


def _load_system(name: str):
    if name == "react":
        from systems.react_system import ReactSystem
        return ReactSystem()
    if name == "native_tool":
        from systems.native_tool_system import NativeToolSystem
        return NativeToolSystem()
    if name == "direct_llm":
        from systems.direct_llm_system import DirectLLMSystem
        return DirectLLMSystem()
    if name == "plan_execute":
        from systems.plan_execute_system import PlanExecuteSystem
        return PlanExecuteSystem()
    if name == "autogen":
        from systems.autogen_system import AutoGenSystem
        return AutoGenSystem()
    raise SystemExit("unknown system: %s" % name)


def main():
    if len(sys.argv) < 3 or sys.argv[1] != "--system":
        raise SystemExit("usage: python run.py --system <name> --queries ... --mcp ... --out ...")
    name = sys.argv[2]
    system = _load_system(name)
    return run_batch(system, argv=sys.argv[3:])


if __name__ == "__main__":
    sys.exit(main())
