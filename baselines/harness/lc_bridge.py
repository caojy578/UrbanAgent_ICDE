# -*- coding: utf-8 -*-
"""LangChain 桥:把 MCPPool 的工具转成 LangChain StructuredTool。

给基于 LangChain/LangGraph 的 baseline(react / plan_execute)用。工具的参数 schema
由 MCP 的 inputSchema 动态转成 pydantic 模型,函数体转调 pool.call_tool(记录进 trace、
QPS 退避)。工具报错时返回 "Error: ..." 文本,让框架的循环能看到并重试(对齐 isError 语义)。
"""
import json
from typing import Any, List, Optional

from pydantic import Field, create_model
from langchain_core.tools import StructuredTool

from .mcp_pool import MCPPool, ToolError

_JSON2PY = {"string": str, "number": float, "integer": int,
            "boolean": bool, "array": list, "object": dict}


def _args_model(name: str, schema: dict):
    props = (schema or {}).get("properties", {}) or {}
    required = set((schema or {}).get("required", []) or [])
    fields = {}
    for k, v in props.items():
        pytype = _JSON2PY.get((v or {}).get("type"), Any)
        if k in required:
            fields[k] = (pytype, Field(..., description=(v or {}).get("description", "")))
        else:
            fields[k] = (Optional[pytype], Field(None, description=(v or {}).get("description", "")))
    return create_model("%s_Args" % name, **fields)


def build_langchain_tools(pool: MCPPool) -> List[StructuredTool]:
    tools = []
    for name in pool.tool_names():
        desc, params = pool.tool_meta(name)
        args_model = _args_model(name, params)

        def _make(tool_name):
            def _call(**kwargs):
                clean = {k: v for k, v in kwargs.items() if v is not None}
                try:
                    r = pool.call_tool(tool_name, clean)
                    return r if isinstance(r, str) else json.dumps(r, ensure_ascii=False, default=str)
                except ToolError as e:
                    return "Error: %s" % e
            return _call

        tools.append(StructuredTool.from_function(
            func=_make(name), name=name,
            description=(desc or name)[:1024], args_schema=args_model))
    return tools
