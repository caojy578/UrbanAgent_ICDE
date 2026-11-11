# UrbanEval

250 natural-language requests, 50 in each of FR, CR, SD, CC, and AI.

- `queries/` — the requests given to the agent. Runtime files are the instantiated queries used for the reported runs.
- `gt_spec/` — human-authored checklists. Stable facts use fixed references. Time-varying and computed claims are graded against the tool observations of that run.
- `verdicts_frozen/` — frozen task verdicts and the metric summaries behind the main tables.

The judge is Qwen3-Max at temperature 0, with system identities masked. Scoring scripts and the judge outputs are under `../evaluation/`.
