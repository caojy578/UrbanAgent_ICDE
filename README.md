# UrbanAgent ICDE artifact

Supplemental code and data for the ICDE submission *UrbanAgent: A Tool-Augmented Agent for Cross-System Urban Tasks*.

The archive has four parts. Live reruns need an OpenAI-compatible endpoint and the same MCP tool servers used in the paper. Keys are not included.

```text
urbanagent/                  Reference agent: cognition, ReAct core, tool invocation, synthesis
urbaneval/                   250 queries, per-query criteria, frozen verdicts
baselines/                   Native tool-calling, ReAct, Plan-and-Execute, AutoGen
evaluation/                  Scoring scripts and frozen judge outputs
results/
  tool_augmented/            RQ1–RQ3 tool-augmented runs (4 backbones × 5 systems × 250 queries)
  single_llm/                Ten single LLMs without tools
  ablation_gpt-5.6-sol/      RQ4 leave-one-out ablation on one backbone
carla_emergency_response/    CARLA emergency prototype (bridge, controller, dashboard)
```

## What matches the paper

- Main comparison (Table II). Tool-augmented systems share a backbone, the MCP tools, temperature 1.0, and a budget of 25 model calls or 600 seconds. The controlled backbone is GPT-5-mini. The other backbones are Gemini-2.5-flash, DeepSeek-V4-flash, and Qwen3-235B-A22B. On GPT-5-mini, UrbanAgent's overall task success rate is 0.71 (177/250).
- Single LLMs (Table III). Ten models prompted without tools or live observations.
- Ablation (Table IV). One backbone, GPT-5.6-sol, on all 250 queries. Five variants each turn off one module of the full system. These rates are not comparable to Table II.
- Case studies. Healthcare coordination uses the UrbanAgent tool loop. The emergency prototype is the three programs under `carla_emergency_response/`.

## Layout of the recorded runs

`results/tool_augmented/`

| Directory | Paper backbone |
| --- | --- |
| `gpt5mini` | GPT-5-mini |
| `gemini25flash` | Gemini-2.5-flash |
| `deepseek_v4_flash` | DeepSeek-V4-flash |
| `qwen3_235b_a22b` | Qwen3-235B-A22B |

Each backbone directory contains `urban_agent`, `native_tool`, `react`, `plan_execute`, and `autogen`. Per-query files are grouped by FR, CR, SD, CC, and AI. UrbanAgent runs also store `_raw_logs/`.

`results/single_llm/`

| Directory | Paper model |
| --- | --- |
| `gpt5mini` | GPT-5-mini |
| `gemini25flash` | Gemini-2.5-flash |
| `deepseek_v4_flash` | DeepSeek-V4-flash |
| `qwen3` | Qwen3-235B-A22B |
| `gpt5` | GPT-5 |
| `opus45` | Claude-Opus-4.5 |
| `gemini31pro` | Gemini-3-Pro |
| `dsr1_ca` | DeepSeek-R1 |
| `kimik25` | Kimi-K2.5 |
| `glm5` | GLM-5 |

Frozen task verdicts and metric summaries are in `urbaneval/verdicts_frozen/`. Judge outputs for those runs are in `evaluation/records/`.

## Ablation

See `results/ablation_gpt-5.6-sol/README.md`. The switches live in `urbanagent/urban_agent/config.py` and are selected only by environment variables. The full system and every variant use `URBAN_AGENT_MODEL=gpt-5.6-sol`.

| Switch | Paper row |
| --- | --- |
| (defaults) | Full System |
| `URBAN_AGENT_SKIP_COGNITION=1` | w/o Cognition |
| `URBAN_AGENT_CORE=static_dag` | Static Plan |
| `URBAN_AGENT_OBS_RECOVERY=off` | w/o Obs. Recovery |
| `URBAN_AGENT_INVOKE_MODE=text_json` | w/o Schema Inv. |
| `URBAN_AGENT_SYN=off` | w/o Final Rewrite |

## CARLA emergency prototype

`carla_emergency_response/` is not part of the UrbanEval numbers. It is the simulation in Section VI: `carla_bridge` talks to CARLA, `urban_agent` plans and issues commands, and `urban_frontend` is the dashboard.

## Running the reference agent

```bash
cd urbanagent
pip install -r requirements.txt
export OPENAI_API_KEY=...
export OPENAI_BASE_URL=...          # OpenAI-compatible endpoint
export URBAN_AGENT_MODEL=gpt-5-mini # main-table backbone
python -m urban_agent.cli "..." --mcp /path/to/mcp.json
```

Do not commit API keys. Live tool results change over time. The files under `results/` are the runs behind the tables.
