# RQ4 ablation

One backbone, GPT-5.6-sol, for the full system and all five variants. Same 250 UrbanEval queries, same MCP tools, temperature 1.0, and the same budget of 25 model calls or 600 seconds. Each variant disables exactly one module.

These scores are not comparable to the GPT-5-mini main table. Read a row only against the full row.

| Configuration | Environment | Overall TSR |
| --- | --- | --- |
| Full System | defaults (`react`, schema calls, observation recovery on, synthesis rewrite) | 0.732 |
| w/o Cognition | `URBAN_AGENT_SKIP_COGNITION=1` | 0.696 |
| w/o Obs. Recovery | `URBAN_AGENT_OBS_RECOVERY=off` | 0.684 |
| w/o Schema Inv. | `URBAN_AGENT_INVOKE_MODE=text_json` | 0.532 |
| Static Plan | `URBAN_AGENT_CORE=static_dag` | 0.552 |
| w/o Final Rewrite | `URBAN_AGENT_SYN=off` | 0.708 |

`aggregate.md` is the 250-query rollup: task success by type, clarification, Level-2 process metrics, and token cost. Internal run ids in that file map to the rows above as `ua_full`, `ua_no_cognition`, `ua_no_obs_recovery`, `ua_no_schema_invoke`, `ua_static_dag`, and `ua_syn_off`.
