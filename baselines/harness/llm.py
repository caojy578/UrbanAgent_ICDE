# -*- coding: utf-8 -*-
"""LLM 接入:两个适配器,共用同一套预算/用量/中转站重试逻辑。

  * RawLLM         —— 给"我自控循环"的 baseline(native_tool):直接 openai 客户端,
                      每次 chat 前 check 预算、后 tick + 累加 usage。
  * make_langchain_llm —— 给 LangChain/LangGraph 框架(react / plan_execute):返回
                      配置好的 ChatOpenAI + 一个回调,回调把预算和 usage 挂到同一套
                      Budget/Usage 上(框架内部每次 LLM 调用都会触发)。

中转站(chatanywhere)瞬时故障:openai 客户端层 max_retries + timeout 兜底;
预算 timeout 优先于网络等待(deadline 到就抛 BudgetExceeded)。
"""
from typing import Any, Dict, List, Optional

from openai import OpenAI, BadRequestError

from . import config
from .budget import Budget, Usage, BudgetExceeded, ContextOverflow


class RawLLM:
    """裸 openai 封装,给自控循环用。"""

    def __init__(self, budget: Budget, usage: Usage):
        self.client = OpenAI(api_key=config.API_KEY, base_url=config.BASE_URL,
                             max_retries=4, timeout=180.0)
        self.budget = budget
        self.usage = usage

    def chat(self, messages: List[Dict[str, Any]],
             tools: Optional[List[Dict[str, Any]]] = None,
             tool_choice: Optional[str] = None) -> Any:
        self.budget.check()
        kwargs: Dict[str, Any] = dict(model=config.MODEL, messages=messages,
                                      temperature=config.TEMPERATURE)
        if tools:
            kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = tool_choice
        try:
            resp = self.client.chat.completions.create(**kwargs)
        except BadRequestError as err:                 # relay 400:上下文超长
            s = str(err).lower()
            if "context_length" in s or "maximum context" in s or "too long" in s:
                raise ContextOverflow(str(err)[:200])
            raise
        u = getattr(resp, "usage", None)
        self.usage.add(getattr(u, "prompt_tokens", 0) if u else 0,
                       getattr(u, "completion_tokens", 0) if u else 0,
                       getattr(resp, "model", None))
        self.budget.tick()
        # relay 上下文溢出时可能回 200 但 choices 为空/None → 别对 None 取下标(TypeError)
        choices = getattr(resp, "choices", None)
        if not choices:
            raise ContextOverflow("empty choices (prompt≈%s tok)"
                                  % (getattr(u, "prompt_tokens", 0) if u else 0))
        return choices[0].message


# --------- LangChain / LangGraph 适配 ---------

def make_langchain_llm(budget: Budget, usage: Usage):
    """返回 (ChatOpenAI, callback);把 callback 传给 agent 的 config 即可让框架内部
    每次 LLM 调用都计入预算与 usage。"""
    from langchain_openai import ChatOpenAI
    from langchain_core.callbacks import BaseCallbackHandler

    # prompt 字符阈值:超过即判 context 撑爆(≈ 200k token)。正常运行 prompt 通常 <150k
    # 字符;只有工具吐回超大 payload(如 SD-24 地震 1.35MB)才会越线。与 RawLLM 的
    # ContextOverflow 守卫同义——在 relay 用 503「输入过长」打回**之前**主动、确定性地判失败,
    # 免得 LangChain 路径把这类模型行为失败误记成 framework_error 而无限 rerun。
    CTX_CHAR_LIMIT = 800_000

    def _prompt_chars(messages):
        total = 0
        for batch in messages or []:
            for m in batch or []:
                c = getattr(m, "content", m)
                total += len(c if isinstance(c, str) else str(c))
        return total

    class _BudgetUsageCB(BaseCallbackHandler):
        raise_error = True               # 否则 LangChain 只打日志、吞掉 callback 里抛的异常

        def on_chat_model_start(self, serialized, messages, **kwargs):
            budget.check()
            n = _prompt_chars(messages)
            if n > CTX_CHAR_LIMIT:
                raise ContextOverflow("prompt≈%d chars > %d (工具返回撑爆上下文)"
                                      % (n, CTX_CHAR_LIMIT))

        def on_llm_start(self, *args, **kwargs):
            budget.check()               # 超预算则抛 BudgetExceeded,中断框架

        def on_llm_end(self, response, **kwargs):
            budget.tick()
            # 累加 token(LangChain 把 usage 放在 llm_output 或 generations 的 metadata)
            out = getattr(response, "llm_output", None) or {}
            tok = out.get("token_usage") or out.get("usage") or {}
            pt = tok.get("prompt_tokens", 0)
            ct = tok.get("completion_tokens", 0)
            mid = out.get("model_name")
            if not pt and getattr(response, "generations", None):
                # 新版把 usage_metadata 挂在 message 上
                try:
                    msg = response.generations[0][0].message
                    um = getattr(msg, "usage_metadata", None) or {}
                    pt = um.get("input_tokens", 0)
                    ct = um.get("output_tokens", 0)
                    mid = getattr(msg, "response_metadata", {}).get("model_name", mid)
                except Exception:  # noqa: BLE001
                    pass
            usage.add(pt, ct, mid)

    llm = ChatOpenAI(model=config.MODEL, temperature=config.TEMPERATURE,
                     api_key=config.API_KEY, base_url=config.BASE_URL,
                     max_retries=4, timeout=180.0)
    return llm, _BudgetUsageCB()
