# UrbanAgent — 单智能体工具调用 Workflow 框架

论文《UrbanAgent》方法章的参考实现。报告配置使用单一 LLM 策略、ReAct
执行核心和 evidence-aligned rewrite synthesis，不使用多智能体协作或预先固定的
工具链。

## 与论文的对应关系

整体映射:

```
Q --f_cog--> U --[reason <-> invoke/observe]--> (O, R_hat)
  --f_syn--> R
```

| 论文机制 | 代码位置 |
|---|---|
| Cognition: Q → U = ⟨I, E, C_hard, C_soft, M⟩；缺失信息作为执行前置条件 | `workflow/cognition.py` |
| Reasoning–Execution Core: 基于已有观测自适应选择下一动作或提交草稿 | `workflow/react_core.py` |
| Tool Invocation: 全工具面 function calling、调用记录、错误反馈、空结果与错城市检查 | `workflow/react_core.py`, `tools/base.py` |
| Synthesis: 清理草稿、对齐多源观测与任务约束、提交最终回答 | `workflow/synthesis.py::run_synthesis_react` |
| MCP 风格统一工具库 T = {τ_1..τ_m}: 元数据描述、来源与 JSON Schema | `tools/base.py`, `tools/*.py` |
| 单智能体 | 同一个 `LLM` 实例贯穿 cognition、ReAct 和 synthesis (`agent.py`) |

旧 DAG 路径仍保留用于兼容性实验，可通过 `URBAN_AGENT_CORE=dag` 启用；论文
结果使用默认的 `react` + `rewrite` 配置。

工具库覆盖实验涉及的城市计算方向:高德 GIS/POI/路线/IP/天气(需 `AMAP_KEY`)、Open-Meteo 全球天气与地理编码(免钥)、USGS 地震(免钥)、碳排放确定性计算器(本地)。

## 使用

```bash
export OPENAI_API_KEY=sk-...            # 任意 OpenAI 兼容后端
export OPENAI_BASE_URL=...              # 可选,默认官方
export URBAN_AGENT_MODEL=gpt-5-mini     # 默认即 gpt-5-mini(论文实验基模)
export AMAP_KEY=...                     # 内置高德工具需要(MCP 模式不需要)

# 单条查询(内置本地工具,调试用)
python -m urban_agent.cli "我现在在北京大学,3公里内找评分4.5以上的川菜馆并规划步行路线" --trace out.json

# 单条查询(共享 MCP 工具集 = 论文对比实验口径)
python -m urban_agent.cli "..." --mcp ../mcp.linux.json
```

## 论文对比实验(与 5 个 baseline 同口径)

UrbanAgent 必须与 baseline 使用**同一套 MCP 工具面**(`mcp.json`,排除 filesystem)、
同一基模(gpt-5-mini,T=1.0)、同一预算(每条查询 ≤25 次 LLM 调用或 10 分钟)。

```bash
# 1) 验活共享 MCP 服务器并导出工具清单(与师弟侧 tools_manifest.json 对 diff)
python -m urban_agent.mcp_manifest --mcp ../mcp.linux.json --out tools_manifest.json

# 2) 批量跑当天实例化的查询(串行;断点续跑,已有结果自动跳过,绝不覆盖)
python -m urban_agent.batch \
    --queries ../baseline_experiments/queries/runtime/queries_<date>.json \
    --mcp ../mcp.linux.json \
    --out ../baseline_experiments/results/urban_agent
```

结果文件与 `baseline_experiments/schema/result_example.json` 逐字段一致
(`baseline="urban_agent"`),可直接用 `scripts/validate_results.py` 校验;
完整 trace 同时存到 `<out>/_raw_logs/<query_id>.json`。手册硬规则已在代码内
强制:只喂 `query` 字段、澄清问题即终态、token 用量仅取 API usage 字段、
工具原始返回全量保存、超预算记 `termination_reason=step_limit|timeout`。

MCP 客户端为自带最小实现(`tools/mcp_client.py`,stdio + SSE,Python 3.8
可用,无需官方 mcp SDK);Windows 风格的 `cmd /c npx` 配置在 Linux 下自动翻译。
本机没装的服务器(如师弟机器上的本地仓库)会被明确报告为 unavailable,
正式跑会拒绝启动,避免"少工具跑完还以为公平"。

Python API:

```python
from urban_agent import UrbanAgent
solution = UrbanAgent().run("查询近7天台湾花莲附近4级以上地震")
print(solution.answer)
```

## Trace 与过程层指标

每次运行输出结构化 trace(默认 `traces/<id>.json`),含结构化认知结果、ReAct 草稿、逐次工具调用记录(含失败与重试)、最终回答、token 用量与时延。这些记录提供 UrbanEval 过程层指标(工具调用完备率 TIC、顺序正确率 IOA、主动增强率 VPAR)与效率指标的原始数据。报告配置不生成预先固定的任务 DAG。

## Ablation (RQ4)

The component ablation uses one backbone, `gpt-5.6-sol`, for the full system and every variant. It is not comparable to the GPT-5-mini main table. Each variant changes one switch and leaves the others at the reported defaults (ReAct core, schema-constrained calls, observation recovery on, synthesis rewrite on). Budget remains 25 model calls or 600 seconds, temperature 1.0.

```bash
export URBAN_AGENT_MODEL=gpt-5.6-sol
# full
# w/o cognition
URBAN_AGENT_SKIP_COGNITION=1
# static plan
URBAN_AGENT_CORE=static_dag
# w/o observation recovery
URBAN_AGENT_OBS_RECOVERY=off
# w/o schema-constrained invocation
URBAN_AGENT_INVOKE_MODE=text_json
# w/o final rewrite
URBAN_AGENT_SYN=off
```

Aggregated 250-query scores are in `../results/ablation_gpt-5.6-sol/`.

## 行为要点

- **模糊/不完整查询**:认知模块检出缺失参数 → 返回 `status=clarification` 与追问,不带猜测参数执行(可用 `--no-clarify` 关闭,用于消融)。
- **条件分支查询**("下雨坐地铁否则骑行"):推理--执行核心先调用工具观测条件,再根据观测选择后续工具,不预先固定完整调用链。
- **成功外壳内的错误**(如高德 status=0/限流):工具层将错误转为显式观测并反馈给 ReAct 循环;综合阶段随后清理草稿,并将回答与已有观测及任务约束对齐。该阶段是同一 LLM 的提示式改写,不是独立的确定性校验器。
