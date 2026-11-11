# VPAR 判分补齐与口径修复(2026-07-28)

## 背景问题
`judge_trajectory.py` 判分异常时 `continue` 会**静默丢行**(见 README 记的
"traj 47% 被丢事故"同源)。结果:各基模块 Level-2(SD+CC)轨迹判**漏判 34 条**,
且各方法漏判数不同 → VPAR 分母 95/93/91/97/90 不一致,审稿人会质疑。

## 修复
1. **补判**:对"当前结果快照里 ≥1 工具调用、却未判"的运行,用**同一判官
   (qwen3-max, 温度0)、同 rubric** 补判。共补 GPT-5-mini 4 + Gemini 7 +
   DeepSeek 7 = 18 条(补判原始输出在 `../judge_traj_rejudge/`)。
2. **合并**:`<block>/traj_<method>.jsonl` = 定版判分 ∪ 补判(不改任何既有 verdict)。
3. **口径(B)**:VPAR = 有效增强数 / (Level-2 中**当前快照实际发起过 ≥1 工具调用**的运行数)。
   0 调用运行无执行、增强 N/A,不计入分母(脚本本来的设计)。
   分子/分母都严格限定在"当前快照 withtool"集合内,避免把"定版判过但快照现为0调用"
   的陈旧 verdict 误计。

## 结论:数字基本不变(证明现表本就基本正确,只是漏判未被发现)
`SUMMARY_VPAR_completed.json`(顺序 Native/ReAct/Plan/AutoGen/UrbanAgent):
- GPT-5-mini: 0.83 / 0.84 / 0.84 / 0.83 / **0.96**   (UA 95/99)
- Gemini:     0.79 / 0.82 / 0.90 / **0.93** / 0.86
- DeepSeek:   0.96 / 0.95 / **0.98** / 0.92 / 0.94
- Qwen3:      0.46 / 0.53 / 0.72 / 0.62 / **0.86**

论文表 tab:main_results 的 VPAR 列与正文(95 of 99;分项 refine 85 / retrieval 54 /
recovery 8 / xval 10;0.96 vs 0.84 strongest baseline)已据此更新。
