# -*- coding: utf-8 -*-
"""Connect the shared MCP servers, verify them, export tools_manifest.json.

Mirrors the baseline side's server-liveness check (manual §4) so both sides
can diff their manifests and confirm an identical tool surface.

    python -m urban_agent.mcp_manifest --mcp ../mcp.json --out tools_manifest.json
"""
import argparse
import json
import sys
from typing import List, Optional

from .tools.mcp_registry import build_mcp_registry, close_registry, export_manifest


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="urban_agent.mcp_manifest")
    parser.add_argument("--mcp", required=True, help="path to mcp.json")
    parser.add_argument("--out", default="tools_manifest.json")
    args = parser.parse_args(argv)

    registry, failures = build_mcp_registry(args.mcp)
    try:
        manifest = export_manifest(registry)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)

        by_server = {}
        for entry in manifest:
            by_server.setdefault(entry["server"], []).append(entry["name"])
        print("connected servers (%d):" % len(by_server))
        for server, tools in sorted(by_server.items()):
            print("  %-22s %2d tools: %s" % (server, len(tools), ", ".join(tools)))
        if failures:
            print("\nUNAVAILABLE servers (%d):" % len(failures), file=sys.stderr)
            for name, why in failures.items():
                print("  %-22s %s" % (name, why), file=sys.stderr)
        print("\nmanifest written to %s (%d tools)" % (args.out, len(manifest)))
    finally:
        close_registry(registry)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
