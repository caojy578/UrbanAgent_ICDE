# -*- coding: utf-8 -*-
from .base import Tool, ToolExecutionError, ToolRegistry, tool
from . import amap, carbon, earthquake, weather


def build_default_registry() -> ToolRegistry:
    """Assemble the unified urban tool library T_MCP."""
    reg = ToolRegistry()
    amap.register(reg)
    weather.register(reg)
    earthquake.register(reg)
    carbon.register(reg)
    return reg


__all__ = ["Tool", "ToolRegistry", "ToolExecutionError", "tool", "build_default_registry"]
