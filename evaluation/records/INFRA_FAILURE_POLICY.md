# 基础设施故障策略(2026-07-13 定案,对全 6 系统 × 3 基模一致)

外部 MCP 工具(高德/Yelp/酒店/USGS 等)有间歇性宕机。若"出故障就重跑",永不收敛,且滑向"重跑到好看"。故定死如下策略,事先注册、统一适用、不再逐结果重跑。

## ① 分类(按错误签名,不按结果)
- **基础设施故障**:后端 5xx/429、连接/超时、SSE 会话过期、Yelp "Unable to fetch"——换任何系统在那一刻调都一样挂。签名见 `rule_metrics._INFRA_SIGS`。
- **agent 归因**:选错工具(境外地址派高德→ENGINE_RESPONSE_DATA_ERROR)、参数错(裸 400)、自身规划烂烧光预算。**故意不计入基础设施签名**,照常计成本与正确率。

## ② 一次性清障后冻结
仅当某后端**持续宕机数小时**(酒店 MCP、Yelp 两次)做一次统一重跑清障。之后**孤立随机抖动不再重跑**,由 ③ 的报告口径处理。这是打破"重跑跑步机"的关键规则。

## ③ 度量在"基础设施干净子集"上算
- 一次 run 判为污染 `infra_tainted=True`:存在某工具其**所有**调用都失败且含基础设施签名(该后端整段 run 不可用)。agent 已成功兜底的偏发抖动**不算**污染(那部分成本是 agent 行为)。
- **效率层**(tokens/calls/延迟/P95/预算触发/Tok·Time per Success):对干净 run 取值,污染 run 踢出分母,`n_infra_excluded` 单列报告。→ 效率对将来抖动**稳定**:再抖一条只是排除数+1,不撼动均值。
- **TSR**:污染 run 不算 agent 失败(排除+计数),不记 0。

## 实现
- `rule_metrics.py`:`infra_tainted()` 检测 + 每行 `infra_tainted` 字段 + summary `n_infra_excluded`/`n_eff_denom`;效率 `_avg` 用干净谓词。
- `aggregate.py`:效率层与 Tok/Time·per·Success 均在干净子集上算,报表加 `n_excl` 列。
- 单测:酒店受害题 8/8 判污染;正常题不误伤;**美国题高德失败正确判为 agent 归因(不排除)**。

## 论文 protocol 写法(拟)
"Runs in which an external service was unavailable for the entire call (backend 5xx/429, connection/timeout, or session expiry) are excluded from efficiency and success aggregation and reported separately (n=X, Y%); tool-selection errors and self-inflicted budget exhaustion are retained as system behavior."

## 修订(2026-07-13,用户定:重试优先于排除)
用户拍板:baseline 跑时工具连接失败,**优先重跑**(每次新建会话,酒店题秒级完成、赶在会话过期前,大概率成功),而非直接排除。排除退为**安全网**:有界重试(3 轮)后仍污染的才排除+报告。
- 官方 harness(baselines_official)用官方 mcp SDK,不港移 ua 的自愈代码,保持纯净;靠查询级重跑收敛。
- 实现:scripts 级 infra_retry.py(三基模×6系统,逐轮重检 infra_tainted 并重跑残留,≤3轮),排在 DeepSeek 链后自动触发。
- rule_metrics/aggregate 的排除逻辑保留,只对重试后残留生效。
