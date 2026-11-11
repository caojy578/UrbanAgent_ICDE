# 评测聚合摘要

Backbone for every system below: GPT-5.6-sol. One model, 250 queries. Not comparable to the GPT-5-mini main table.

系统: ua_full, ua_no_cognition, ua_no_obs_recovery, ua_no_schema_invoke, ua_static_dag, ua_syn_off


## 结果层 · TSR(overall / 各类型;AI 列=GuessFree@AI)

| 系统 | ALL | FR | CR | SD | CC | AI(=GuessFree) | 未判定 |
|---|---|---|---|---|---|---|---|
| ua_full | 0.732 | 0.68 | 0.52 | 0.8 | 0.68 | 0.98 | 0 |
| ua_no_cognition | 0.696 | 0.72 | 0.56 | 0.74 | 0.58 | 0.88 | 0 |
| ua_no_obs_recovery | 0.684 | 0.64 | 0.56 | 0.66 | 0.58 | 0.98 | 0 |
| ua_no_schema_invoke | 0.532 | 0.6 | 0.3 | 0.42 | 0.36 | 0.98 | 0 |
| ua_static_dag | 0.552 | 0.56 | 0.42 | 0.48 | 0.32 | 0.98 | 0 |
| ua_syn_off | 0.708 | 0.72 | 0.54 | 0.7 | 0.6 | 0.98 | 0 |

## 结果层 · 澄清指标(Ask/Hit 诊断;GuessFree 已进上表 AI 列)

| 系统 | GuessFree@AI | Ask@AI | Hit@AI |
|---|---|---|---|
| ua_full | 0.98 | 0.98 | 1.0 |
| ua_no_cognition | 0.88 | 0.92 | 1.0 |
| ua_no_obs_recovery | 0.98 | 0.98 | 1.0 |
| ua_no_schema_invoke | 0.98 | 0.98 | 1.0 |
| ua_static_dag | 0.98 | 0.98 | 1.0 |
| ua_syn_off | 0.98 | 0.98 | 1.0 |

## 过程层 · L2 正式表(TIC/IOA/VPAR;Seq=顺序依赖 SD / Cond=条件组合 CC)

| 系统 | TIC-Seq | TIC-Cond | IOA-Seq | IOA-Cond | VPAR-Seq | VPAR-Cond |
|---|---|---|---|---|---|---|
| ua_full | 0.959 | 0.914 | 0.909 | 0.963 | 0.94 | 0.917 |
| ua_no_cognition | 0.934 | 0.923 | 0.947 | 0.94 | 0.939 | 0.898 |
| ua_no_obs_recovery | 0.929 | 0.918 | 0.95 | 0.94 | 0.959 | 0.959 |
| ua_no_schema_invoke | 0.564 | 0.508 | 0.933 | 0.967 | 0.933 | 0.857 |
| ua_static_dag | 0.809 | 0.716 | 0.968 | 1.0 | 0.551 | 0.327 |
| ua_syn_off | 0.949 | 0.899 | 0.952 | 0.907 | 0.96 | 0.938 |

## 过程层 · VPAR 四分类(Cond=CC;比率=该类出现题数/有轨迹题数)

| 系统 | n_traj | err_rec | refine | cross | expand |
|---|---|---|---|---|---|
| ua_full | 48 | 0.125 | 0.896 | 0.062 | 0.354 |
| ua_no_cognition | 49 | 0.143 | 0.857 | 0.061 | 0.469 |
| ua_no_obs_recovery | 49 | 0.061 | 0.939 | 0.02 | 0.327 |
| ua_no_schema_invoke | 28 | 0.357 | 0.821 | 0.036 | 0.321 |
| ua_static_dag | 49 | 0.0 | 0.245 | 0.0 | 0.122 |
| ua_syn_off | 48 | 0.125 | 0.917 | 0.083 | 0.583 |

## 效率层(已排除基础设施故障 run;n_excl=排除数)

| 系统 | n_excl | tok均值 | tok P95 | 时延均值 | 时延P95 | Tok/成功 | Time/成功 | 预算触发 |
|---|---|---|---|---|---|---|---|---|
| ua_full | 18 | 59726.685 | 132954.9 | 25.583 | 54.7 | 81991.7 | 35.1 | 0.0 |
| ua_no_cognition | 25 | 55054.133 | 127988.2 | 21.756 | 43.8 | 79405.0 | 31.4 | 0.0 |
| ua_no_obs_recovery | 18 | 59182.427 | 154801.3 | 26.618 | 56.5 | 86900.8 | 39.1 | 0.0 |
| ua_no_schema_invoke | 0 | 38286.376 | 148454.9 | 21.11 | 52.9 | 71966.9 | 39.7 | 0.0 |
| ua_static_dag | 0 | 14403.404 | 27354.2 | 20.964 | 39.0 | 26093.1 | 38.0 | 0.0 |
| ua_syn_off | 20 | 57516.987 | 142547.8 | 22.869 | 49.4 | 81659.9 | 32.5 | 0.0 |

## TSR 显著性(McNemar vs ua_full)

| 系统 | ref胜 | sys胜 | p |
|---|---|---|---|
| ua_no_cognition | 23 | 14 | 0.1877 |
| ua_no_obs_recovery | 20 | 8 | 0.0357 |
| ua_no_schema_invoke | 53 | 3 | 0.0 |
| ua_static_dag | 52 | 7 | 0.0 |
| ua_syn_off | 14 | 8 | 0.2863 |
