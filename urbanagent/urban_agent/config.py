# -*- coding: utf-8 -*-
"""Global configuration for the UrbanAgent workflow framework.

All values can be overridden via environment variables so that the same
codebase runs against different OpenAI-compatible backends (GPT-4o, GPT-5.x,
DeepSeek, Qwen, ...) without code changes.
"""
import os


class Config:
    # ---- LLM backend (OpenAI-compatible) ----
    api_key = os.environ.get("URBAN_AGENT_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("URBAN_AGENT_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or None
    # Paper (Implementation Details): base model gpt-5-mini for all systems
    model = os.environ.get("URBAN_AGENT_MODEL", "gpt-5-mini")
    # Paper (Implementation Details): temperature fixed at T = 1.0
    temperature = float(os.environ.get("URBAN_AGENT_TEMPERATURE", "1.0"))

    # ---- Per-query budget (parity with the baseline manual) ----
    # <= 25 LLM calls or 10 minutes per query, whichever comes first
    max_llm_calls_per_query = int(os.environ.get("URBAN_AGENT_MAX_LLM_CALLS", "25"))
    query_timeout_s = float(os.environ.get("URBAN_AGENT_QUERY_TIMEOUT", "600"))

    # ---- Shared MCP toolset (same surface as the five baselines) ----
    mcp_config = os.environ.get("URBAN_AGENT_MCP_CONFIG", "")

    # ---- Execution module ----
    # Paper (Implementation Details): closed-loop retry capped at K = 3
    max_retries_per_node = int(os.environ.get("URBAN_AGENT_MAX_RETRIES", "3"))
    # Upper bound of tool invocations inside one atomic node (guards runaway loops)
    max_tool_calls_per_node = int(os.environ.get("URBAN_AGENT_MAX_TOOL_CALLS", "6"))
    # Adaptive re-planning: after execute+synthesize, if the observations do not
    # yet satisfy the task, re-plan targeted follow-up nodes and execute them.
    # Breaks the rigidity of a one-shot DAG (0 = disabled, static plan).
    max_replan_rounds = int(os.environ.get("URBAN_AGENT_MAX_REPLAN", "2"))
    # HTTP timeout for tool backends (seconds)
    tool_timeout = float(os.environ.get("URBAN_AGENT_TOOL_TIMEOUT", "20"))
    # ---- Execution backbone (v2) ----
    # "react":      adaptive reason-act-observe loop (reported / full).
    # "static_dag": one-shot plan then execute; no replan; shared rewrite synthesis.
    # "dag":        legacy DAG with replan + DAG-only synthesis (not used in new ablations).
    core = os.environ.get("URBAN_AGENT_CORE", "react")
    # Finalization after the ReAct loop:
    # "rewrite" cleans and aligns the draft with the structured task and all
    # observations (reported configuration); "note" appends the legacy
    # constraint-check note; "off" returns the ReAct draft verbatim.
    react_synthesis = os.environ.get("URBAN_AGENT_SYN", "rewrite")

    # ---- Ablation switches (RQ4, backbone fixed at gpt-5.6-sol) ----
    # Skip f_cog entirely: raw query goes to the executor / synthesizer.
    skip_cognition = os.environ.get("URBAN_AGENT_SKIP_COGNITION", "").strip().lower() in (
        "1", "true", "yes", "on")
    # Runtime observation checks + recovery hints (wrong-city reject, empty-result
    # coaching, retry/provider prompts). Success-call dedup and hard budget stay.
    obs_recovery = os.environ.get("URBAN_AGENT_OBS_RECOVERY", "on").strip().lower() not in (
        "0", "false", "no", "off")
    # "schema" = native function calling; "text_json" = free-text JSON tool calls.
    invoke_mode = os.environ.get("URBAN_AGENT_INVOKE_MODE", "schema").strip().lower()
    # Optional. Leave unset for the reported runs.
    reasoning_effort = (os.environ.get("URBAN_AGENT_REASONING_EFFORT") or "").strip() or None

    # ---- Tool backends ----
    amap_key = os.environ.get("AMAP_KEY", "")

    # ---- Tracing ----
    trace_dir = os.environ.get("URBAN_AGENT_TRACE_DIR", "traces")


config = Config()
