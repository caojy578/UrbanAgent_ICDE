# -*- coding: utf-8 -*-
"""Offline smoke test for the reported ReAct + rewrite pipeline.

Exercises cognition, a failed tool call and recovery in the adaptive loop,
trace persistence, and evidence-aligned answer finalization. No API key is
required.
"""
import json
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["URBAN_AGENT_CORE"] = "react"
os.environ["URBAN_AGENT_SYN"] = "rewrite"

from urban_agent.agent import UrbanAgent          # noqa: E402
from urban_agent.tools import ToolRegistry, ToolExecutionError, tool  # noqa: E402


# ---------------------------------------------------------------- fake tools
def build_test_registry() -> ToolRegistry:
    reg = ToolRegistry()

    calls = {"n": 0}

    @tool(reg, "poi_search", "search restaurants near a location",
          {"type": "object",
           "properties": {"location": {"type": "string"}, "keywords": {"type": "string"}},
           "required": ["location", "keywords"]}, domain="poi")
    def poi_search(location: str, keywords: str):
        # first invocation fails -> must trigger the closed-loop retry (Eq. 3)
        calls["n"] += 1
        if calls["n"] == 1:
            raise ToolExecutionError("QPS limit exceeded, please retry")
        return [
            {"name": "川味观", "rating": 4.7, "distance_km": 1.2},
            {"name": "蜀香居", "rating": 4.2, "distance_km": 0.8},
            {"name": "锦官城", "rating": 4.8, "distance_km": 4.5},
        ]

    return reg


# ---------------------------------------------------------------- fake LLM
class Msg:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class FakeToolCall:
    def __init__(self, cid, name, arguments):
        self.id = cid
        self.function = types.SimpleNamespace(name=name, arguments=json.dumps(arguments))

    def model_dump(self):
        return {"id": self.id, "type": "function",
                "function": {"name": self.function.name,
                             "arguments": self.function.arguments}}


class FakeLLM:
    """Replays a fixed script; asserts the framework routes messages correctly."""
    model = "fake"
    temperature = 0.0

    def __init__(self):
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}
        self.step = 0

    # Cognition is the only JSON turn in the reported pipeline.
    def chat_json(self, system, user, retries=2):
        if "cognition module" in system:
            return {
                "intent": "find a Sichuan restaurant near PKU within 3 km, rating >= 4.5, walking route",
                "entities": [{"type": "location", "value": "北京大学"},
                             {"type": "poi", "value": "川菜馆"}],
                "hard_constraints": [
                    {"attribute": "distance_km", "operator": "<=", "value": 3, "unit": "km"},
                    {"attribute": "rating", "operator": ">=", "value": 4.5}],
                "soft_constraints": [{"objective": "rating", "direction": "max", "weight": 1.0},
                                     {"objective": "distance_km", "direction": "min", "weight": 0.5}],
                "missing_info": [], "clarification_needed": False,
            }
        raise AssertionError("unexpected chat_json system prompt")

    # ReAct turns: call tool -> receive error -> retry -> draft; then rewrite.
    def chat(self, messages, tools=None, tool_choice=None):
        self.usage["calls"] += 1
        if "ANSWER-FINALIZATION" in messages[0]["content"]:
            assert "川味观" in messages[-1]["content"]
            return Msg(content="推荐川味观：评分 4.7，距北京大学 1.2 公里，满足评分不低于 4.5 且距离不超过 3 公里的要求。")
        last = messages[-1]
        if last["role"] == "tool" and last["content"].startswith("TOOL ERROR"):
            # Eq. 3 retry with corrected params
            return Msg(tool_calls=[FakeToolCall("c2", "poi_search",
                                                {"location": "116.31,39.99", "keywords": "川菜馆"})])
        if last["role"] == "tool":
            return Msg(content="川味观评分4.7，距离1.2公里，符合要求。需要我继续搜索其他餐厅吗？")
        return Msg(tool_calls=[FakeToolCall("c1", "poi_search",
                                            {"location": "北京大学", "keywords": "川菜馆"})])


def main():
    agent = UrbanAgent(llm=FakeLLM(), registry=build_test_registry())
    solution = agent.run("我现在在北京大学,想找3公里内评分4.5以上的川菜馆",
                         trace_path="/tmp/urban_agent_smoke_trace.json")

    assert solution.status == "ok", solution.status
    assert "川味观" in solution.answer
    assert "继续搜索" not in solution.answer

    with open("/tmp/urban_agent_smoke_trace.json", encoding="utf-8") as fh:
        trace = json.load(fh)
    execution = trace["stages"]["execution"]
    records = [execution["t1"]["tool_calls"][0], execution["t2"]["tool_calls"][0]]
    assert [r["success"] for r in records] == [False, True], records
    assert "QPS limit" in records[0]["error"]
    assert trace["stages"]["react_draft"].endswith("？")
    assert trace["stages"]["solution"]["answer"] == solution.answer

    print("OFFLINE SMOKE TEST PASSED")
    print("  final:", solution.answer)
    print("  retry chain:", [(r["tool"], r["success"]) for r in records])
    print("  trace: /tmp/urban_agent_smoke_trace.json")


if __name__ == "__main__":
    main()
