# -*- coding: utf-8 -*-
"""共享配置:从环境变量读,和 UrbanAgent 一套底座参数保持一致。"""
import os

# 底座模型(手册 §3.0:统一 gpt-5-mini,temperature=1.0)
MODEL = os.environ.get("URBAN_AGENT_MODEL", "gpt-5-mini")
TEMPERATURE = float(os.environ.get("URBAN_AGENT_TEMPERATURE", "1.0"))
API_KEY = os.environ.get("OPENAI_API_KEY", "EMPTY")
BASE_URL = os.environ.get("OPENAI_BASE_URL")

# 每条查询预算(手册 §3.0:≤25 次 LLM 调用 或 10 分钟,先到为准)
MAX_LLM_CALLS = int(os.environ.get("URBAN_MAX_LLM_CALLS", "25"))
MAX_SECONDS = float(os.environ.get("URBAN_MAX_SECONDS", "600"))

# 工具面(手册 §4:排除 filesystem;地图只用高德等已在 mcp.linux.json 定稿)
EXCLUDE_SERVERS = ["filesystem"]

# 高德免费 key QPS 限流:每秒限流退避重试(与 UrbanAgent 的 mcp_registry 一致)
QPS_MAX_RETRY = 6

# 查询间隔(手册 §5.4:高德 QPS,连续查询间 sleep)
SLEEP_BETWEEN_QUERIES = 1.5
