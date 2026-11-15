---
name: rloop-parallel-fanout
description: Scope independent work under one shared budget. Use this when asked to fan out, parallelize experiments, compare variants, or choose a best-of-N research pattern.
---

# Choose bounded independent work

Use the scientist's or engineer's own coding agent to choose the pattern:
independent comparison, dependent pipeline, cheap screening or a control-gated
best-of-N. State dependencies before choosing concurrency.

The planted-signal CLI runs the registered best-of-N campaign with controls
first. It does not expose arbitrary dependency graphs or a generic fanout
command. Use `rloop status PROJECT` to inspect attempts, then
`rloop run PROJECT --backend fake` for the offline campaign.

For supported pre-final contract changes, specify seeds, variants and limits
in `contract.json`, then `rloop plan PROJECT --reason "Explain bounded fanout"`.
All arms share attempt, time and cost limits; extra workers do not create budget.
Keep worker workspaces separate and evaluator, holdout and database on the
coordinator side so parallelism cannot leak evaluation answers.
Stop on exhausted limits; do not retry until a desired scientific result appears.
A real backend needs separate explicit authorization; this workflow is offline.

Read [DESIGN](../../docs/DESIGN.md) for available pattern policies,
[GUIDE](../../docs/GUIDE.md) for the campaign and
[LESSONS](../../docs/LESSONS.md) for observed limits.
