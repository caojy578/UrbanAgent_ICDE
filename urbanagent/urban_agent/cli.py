# -*- coding: utf-8 -*-
"""Command-line entry: python -m urban_agent.cli "查询..." [--trace out.json]"""
import argparse
import sys

from .agent import UrbanAgent


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="urban_agent",
        description="UrbanAgent — single-agent tool-calling workflow "
                    "(cognition → planning → execution → synthesis)")
    parser.add_argument("query", help="natural-language urban query")
    parser.add_argument("--trace", default=None, help="path to write the JSON trace")
    parser.add_argument("--mcp", default=None,
                        help="mcp.json path: use the shared MCP toolset instead of "
                             "the built-in local tools (as in the paper experiments)")
    parser.add_argument("--no-clarify", action="store_true",
                        help="never ask for clarification; execute with best-effort "
                             "parameters (for ablation only)")
    args = parser.parse_args()

    registry = None
    if args.mcp:
        from .tools.mcp_registry import build_mcp_registry
        registry, failures = build_mcp_registry(args.mcp)
        for name, why in failures.items():
            print("[MCP] server %s unavailable: %s" % (name, why), file=sys.stderr)

    agent = UrbanAgent(registry=registry)
    solution = agent.run(args.query, clarify=not args.no_clarify, trace_path=args.trace)

    print("=" * 60)
    print("status:", solution.status)
    if solution.clarification:
        print("clarification:", solution.clarification)
    print("-" * 60)
    print(solution.answer)
    if solution.candidates:
        print("-" * 60)
        for i, c in enumerate(solution.candidates, 1):
            flag = ("PASS" if c.hard_check else "PRUNED") if c.hard_check is not None else "-"
            print("%d. [%s] %s  score=%s  %s" % (
                i, flag, c.name, c.score,
                ("violates: " + "; ".join(c.violated)) if c.violated else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
