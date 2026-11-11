# -*- coding: utf-8 -*-
"""Unified tool library T = {tau_1, ..., tau_m}.

Every heterogeneous urban service (RESTful API, local computation, database
query) is encapsulated as a tool endpoint with uniform metadata: a name, a
natural-language description and a strongly-typed JSON Schema for its
parameters — following the Model Context Protocol (MCP) convention of the
paper. The reported ReAct core reads this metadata on every turn and passes the
schema to the LLM's function-calling interface. The retained DAG planner uses
the same registry in compatibility experiments.
"""
import inspect
import json
import re
from typing import Any, Callable, Dict, List, Optional


class ToolExecutionError(RuntimeError):
    """Raised by a tool backend; converted to natural-language retry context."""


class Tool:
    def __init__(self, name: str, description: str,
                 parameters: Dict[str, Any], fn: Callable[..., Any],
                 domain: str = "general", server: str = "local"):
        self.name = name
        self.description = description
        self.parameters = parameters      # JSON Schema (type: object)
        self.fn = fn
        self.domain = domain              # one of the urban computing domains
        self.server = server              # origin MCP server ("local" = built-in)

    # ---- MCP-style metadata exposed to the LLM ----
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def __call__(self, **kwargs: Any) -> Any:
        return self.fn(**kwargs)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    @staticmethod
    def _norm(name: str) -> str:
        # strip a trailing " [server/domain]" annotation the planner sometimes
        # copies verbatim from the tool catalogue (e.g. "maps_geo [amap-maps]"),
        # then unify hyphen/underscore and case.
        name = re.sub(r"\s*\[[^\]]*\]\s*$", "", (name or "").strip())
        return name.strip().lower().replace("_", "-")

    def resolve(self, name: str) -> Optional[str]:
        """Canonical tool name: exact match, else hyphen/underscore- and
        case-insensitive match (LLMs often emit find_earthquakes for the
        registered find-earthquakes), else a "server:tool" / "server/tool"
        qualified form (e.g. gemini emits amap-maps:maps_geo verbatim from
        the catalogue). Returns None if genuinely unknown."""
        if name in self._tools:
            return name
        target = self._norm(name)
        for canonical in self._tools:
            if self._norm(canonical) == target:
                return canonical
        # server-qualified form: try the part after the separator, but only
        # accept it when the prefix matches the tool's actual server/domain
        # (avoids mis-resolving a genuinely unknown dotted name).
        for sep in (":", "/"):
            if sep in (name or ""):
                prefix, suffix = name.rsplit(sep, 1)
                cand = self.resolve(suffix.strip())
                if cand is not None:
                    t = self._tools[cand]
                    pref = self._norm(prefix)
                    if pref in (self._norm(getattr(t, "domain", "") or ""),
                                self._norm(getattr(t, "server", "") or "")):
                        return cand
        return None

    def names(self) -> List[str]:
        return sorted(self._tools)

    def schemas(self, names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        tools = [self._tools[n] for n in (names or self.names()) if n in self._tools]
        return [t.schema() for t in tools]

    def catalog(self) -> str:
        """Full tool catalogue injected into the reasoning or planning prompt.

        Renders everything the MCP server exposes for each tool — server
        identity, complete description, and the full input schema (each
        parameter's type, required/optional flag and its own description) —
        so the planner can judge a tool's applicability (coverage region,
        expected argument semantics) instead of guessing from the name.
        """
        lines = []
        for name in self.names():
            t = self._tools[name]
            required = set(t.parameters.get("required", []))
            lines.append("- %s [server: %s]: %s" % (name, t.domain, t.description))
            for pname, spec in t.parameters.get("properties", {}).items():
                lines.append("    %s (%s, %s): %s" % (
                    pname, spec.get("type", "any"),
                    "required" if pname in required else "optional",
                    spec.get("description", "")))
        return "\n".join(lines)

    def invoke(self, name: str, arguments: Dict[str, Any]) -> Any:
        canonical = self.resolve(name)
        tool = self._tools[canonical] if canonical else None
        if tool is None:
            raise ToolExecutionError("unknown tool: %s" % name)
        try:
            return tool(**arguments)
        except ToolExecutionError:
            raise
        except TypeError as err:
            raise ToolExecutionError("parameter error for %s: %s" % (name, err))
        except Exception as err:  # noqa: BLE001 — every backend failure becomes retry context
            raise ToolExecutionError("%s failed: %s" % (name, err))


def tool(registry: ToolRegistry, name: str, description: str,
         parameters: Dict[str, Any], domain: str = "general"):
    """Decorator: register a plain function as a tool endpoint."""
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        registry.register(Tool(name, description, parameters, fn, domain))
        return fn
    return deco
