# -*- coding: utf-8 -*-
"""Bridge MCP servers into the unified tool library T_MCP.

For the paper's comparison experiments UrbanAgent must consume exactly the
same tool surface as the five baselines: the servers declared in the shared
``mcp.json`` (``filesystem`` excluded).  Each remote MCP tool is wrapped as a
:class:`~.base.Tool`, so the four-stage workflow is unchanged — planning
reads the same metadata catalogue, execution passes the same JSON Schemas to
function calling, and every invocation is attributable to its origin server
(the ``server`` field of the per-query result files).
"""
import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from .base import Tool, ToolExecutionError, ToolRegistry
from .mcp_client import MCPServer, MCPError, connect_servers

# servers never exposed to the agent (per the experiment manual)
DEFAULT_EXCLUDE = ["filesystem"]

_NAME_RE = re.compile(r"[^A-Za-z0-9_-]")


def _safe_name(name: str, taken: Dict[str, str], server: str) -> str:
    """OpenAI function names must match [A-Za-z0-9_-]{1,64} and be unique."""
    base = _NAME_RE.sub("_", name).strip("_") or "tool"
    candidate = base[:64]
    if candidate not in taken:
        return candidate
    prefixed = (_NAME_RE.sub("_", server).strip("_") or "srv") + "__" + base
    candidate = prefixed[:64]
    n = 2
    while candidate in taken:
        suffix = "_%d" % n
        candidate = prefixed[:64 - len(suffix)] + suffix
        n += 1
    return candidate


def _extract_result(raw: Dict[str, Any], tool: str) -> Any:
    """Flatten an MCP tools/call result into a value for the workflow.

    Text parts are concatenated *in full* (the manual mandates untruncated
    raw returns); a single JSON-looking text part is parsed so downstream
    stages can address fields.  ``isError`` becomes ToolExecutionError and
    thereby enters the closed-loop retry cycle (Eq. 3) instead of being
    hallucinated over.
    """
    parts: List[str] = []
    for item in raw.get("content", []):
        kind = item.get("type")
        if kind == "text":
            parts.append(item.get("text", ""))
        else:  # image/audio/resource — keep a descriptive stub
            parts.append(json.dumps({k: v for k, v in item.items() if k != "data"},
                                    ensure_ascii=False))
    text = "\n".join(parts)
    if raw.get("isError"):
        raise ToolExecutionError("%s returned error: %s" % (tool, text[:2000]))
    stripped = text.strip()
    if stripped[:1] in ("{", "["):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
    return text


def build_mcp_registry(config_path: str,
                       exclude: Optional[List[str]] = None,
                       call_timeout: float = 60.0,
                       ) -> Tuple[ToolRegistry, Dict[str, str]]:
    """Connect the shared MCP servers and expose their tools as T_MCP.

    Returns ``(registry, failures)``; ``failures`` maps server name to the
    reason it could not be connected.  The caller (batch runner) decides
    whether missing servers abort the experiment.
    """
    servers, failures = connect_servers(
        config_path,
        exclude=list(DEFAULT_EXCLUDE if exclude is None else exclude),
        call_timeout=call_timeout)

    reg = ToolRegistry()
    taken: Dict[str, str] = {}
    for sname, server in servers.items():
        try:
            tools = server.list_tools()
        except MCPError as err:
            failures[sname] = "tools/list failed: %s" % err
            continue
        for t in tools:
            exposed = _safe_name(t.get("name", "tool"), taken, sname)
            taken[exposed] = sname
            reg.register(_wrap(server, t, exposed))

    # keep server handles alive & closable alongside the registry
    reg.mcp_servers = servers  # type: ignore[attr-defined]
    return reg, failures


def _wrap(server: MCPServer, tool_spec: Dict[str, Any], exposed_name: str) -> Tool:
    remote_name = tool_spec.get("name", exposed_name)
    parameters = tool_spec.get("inputSchema") or {"type": "object", "properties": {}}

    def fn(**arguments: Any) -> Any:
        # 高德免费 key 的每秒 QPS 限流(CUQPS_HAS_EXCEEDED_THE_LIMIT)是环境瞬时
        # 故障、约 1 秒内恢复:退避重试,避免把环境限流误当 agent 的工具失败。
        # 仅重试"每秒"限流(CUQPS/QPS),不重试"每日额度用尽"(DAILY,重试无用)。
        attempts = 0
        while True:
            try:
                raw = server.call_tool(remote_name, arguments)
            except MCPError as err:
                raise ToolExecutionError("%s/%s: %s" % (server.name, remote_name, err))
            try:
                return _extract_result(raw, remote_name)
            except ToolExecutionError as err:
                msg = str(err).upper()
                is_qps = ("CUQPS" in msg or "QPS" in msg) and "DAILY" not in msg
                attempts += 1
                if not is_qps or attempts >= 6:
                    raise
                time.sleep(min(0.6 * attempts, 3.0))

    return Tool(exposed_name,
                tool_spec.get("description", "") or remote_name,
                parameters, fn, domain=server.name, server=server.name)


def close_registry(reg: ToolRegistry) -> None:
    for server in getattr(reg, "mcp_servers", {}).values():
        server.close()


def export_manifest(reg: ToolRegistry) -> List[Dict[str, Any]]:
    """tools_manifest.json — same artefact the baseline side exports."""
    manifest = []
    for name in reg.names():
        t = reg.get(name)
        manifest.append({
            "server": getattr(t, "server", "local"),
            "name": name,
            "description": t.description,
            "inputSchema": t.parameters,
        })
    return manifest
