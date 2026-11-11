# -*- coding: utf-8 -*-
"""Thin wrapper around an OpenAI-compatible chat endpoint.

A single ``LLM`` instance is shared by all four workflow stages, i.e. the
framework is a *single-agent* system: one policy network pi drives cognition,
planning, execution and synthesis sequentially.
"""
import json
import re
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI

from .config import config


class LLMError(RuntimeError):
    pass


class BudgetExceeded(RuntimeError):
    """Per-query budget hit; ``reason`` matches the manual's enum."""

    def __init__(self, reason: str):
        super().__init__("budget exceeded: %s" % reason)
        self.reason = reason  # "step_limit" | "timeout"


def _extract_json(text: str) -> Any:
    """Robustly pull a JSON object/array out of a model reply."""
    text = text.strip()
    # strip markdown fences
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # fall back to the outermost {...} or [...]
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise LLMError("model did not return valid JSON: %r" % text[:400])


try:                                   # 中转站瞬时故障:连接错/超时/限流/5xx 应重试而非记 framework_error
    from openai import (APIConnectionError, APITimeoutError, RateLimitError,
                        InternalServerError)
    _RETRYABLE = (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)
except Exception:  # noqa: BLE001
    _RETRYABLE = ()


class LLM:
    def __init__(self, model: Optional[str] = None, temperature: Optional[float] = None):
        # max_retries: SDK 内建重试;外层再包一层带退避的重试兜底中转站抖动
        self.client = OpenAI(api_key=config.api_key or "EMPTY", base_url=config.base_url,
                             max_retries=4, timeout=60.0)
        self.model = model or config.model
        self.temperature = config.temperature if temperature is None else temperature
        # cumulative usage for efficiency evaluation (tokens / query)
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}
        # per-query budget hooks (set by UrbanAgent.run)
        self.max_calls: Optional[int] = None
        self.deadline: Optional[float] = None

    # ------------------------------------------------------------------
    def chat(self, messages: List[Dict[str, Any]],
             tools: Optional[List[Dict[str, Any]]] = None,
             tool_choice: Optional[str] = None,
             stop: Optional[List[str]] = None) -> Any:
        """One raw chat completion; returns the first choice message."""
        if self.max_calls is not None and self.usage["calls"] >= self.max_calls:
            raise BudgetExceeded("step_limit")
        if self.deadline is not None and time.time() >= self.deadline:
            raise BudgetExceeded("timeout")
        kwargs: Dict[str, Any] = dict(model=self.model, messages=messages,
                                      temperature=self.temperature)
        if config.reasoning_effort:
            kwargs["reasoning_effort"] = config.reasoning_effort
        if stop:
            kwargs["stop"] = stop
        if tools:
            kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = tool_choice
        resp = self._create_with_retry(kwargs)
        # exact snapshot id returned by the API (manual: record real model id)
        self.model_id = getattr(resp, "model", None) or getattr(self, "model_id", None)
        if getattr(resp, "usage", None):
            self.usage["prompt_tokens"] += resp.usage.prompt_tokens or 0
            self.usage["completion_tokens"] += resp.usage.completion_tokens or 0
        self.usage["calls"] += 1
        return resp.choices[0].message

    # ------------------------------------------------------------------
    def _create_with_retry(self, kwargs: Dict[str, Any], max_attempts: int = 6) -> Any:
        """中转站瞬时故障(连接错/超时/限流/5xx)时指数退避重试;退避期间若超过
        本条查询 deadline 则抛 BudgetExceeded('timeout'),把它当合法终止而非 infra 故障。"""
        import random
        attempt = 0
        while True:
            try:
                return self.client.chat.completions.create(**kwargs)
            except _RETRYABLE as err:
                attempt += 1
                if attempt >= max_attempts:
                    raise
                delay = min(2.0 ** attempt + random.uniform(0, 1.0), 30.0)
                if self.deadline is not None and time.time() + delay >= self.deadline:
                    raise BudgetExceeded("timeout")
                time.sleep(delay)

    def chat_json(self, system: str, user: str, retries: int = 2) -> Any:
        """Ask for a JSON reply and parse it, with lightweight self-repair."""
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": user}]
        last_err = None
        for _ in range(retries + 1):
            msg = self.chat(messages)
            try:
                return _extract_json(msg.content or "")
            except LLMError as err:
                last_err = err
                messages.append({"role": "assistant", "content": msg.content or ""})
                messages.append({"role": "user",
                                 "content": "Your previous reply was not valid JSON. "
                                            "Reply again with ONLY the JSON object."})
        raise last_err
