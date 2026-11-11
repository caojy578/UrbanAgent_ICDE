# -*- coding: utf-8 -*-
"""每条查询的预算与用量(所有 baseline 共用一套口径)。

预算:≤25 次 LLM 调用 或 10 分钟,先到为准(手册 §3.0)。
用量:严格累加 API 返回的 usage 字段(手册 §6.2:禁 tokenizer 事后估算)。
每条查询开跑前 new 一个 Budget + Usage;运行中框架/循环在每次 LLM 调用时 check + add。
"""
import time
from typing import Optional


class BudgetExceeded(RuntimeError):
    """预算用尽;reason 对齐手册枚举 step_limit / timeout。"""

    def __init__(self, reason: str):
        super().__init__("budget exceeded: %s" % reason)
        self.reason = reason


class ContextOverflow(RuntimeError):
    """模型上下文被工具返回撑爆:relay 回空 choices 或报 context_length_exceeded。
    属**模型行为失败**(裸循环无结果摘要,自己把上万条工具返回灌进 prompt),按失败计、
    不重跑,区别于 infra 抽风的 framework_error(等价于 react 在同题的 timeout)。"""

    def __init__(self, detail: str = ""):
        super().__init__("context overflow: %s" % detail)
        self.detail = detail


class Budget:
    def __init__(self, max_calls: int, max_seconds: float):
        self.max_calls = max_calls
        self.deadline = time.time() + max_seconds
        self.calls = 0

    def check(self):
        """一次 LLM 调用**之前**调:超限抛 BudgetExceeded。"""
        if self.calls >= self.max_calls:
            raise BudgetExceeded("step_limit")
        if time.time() >= self.deadline:
            raise BudgetExceeded("timeout")

    def tick(self):
        """一次 LLM 调用**成功之后**调:计数 +1。"""
        self.calls += 1


class Usage:
    def __init__(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.model_id: Optional[str] = None

    def add(self, prompt: int, completion: int, model_id: Optional[str] = None):
        self.prompt_tokens += prompt or 0
        self.completion_tokens += completion or 0
        if model_id:
            self.model_id = model_id

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens
