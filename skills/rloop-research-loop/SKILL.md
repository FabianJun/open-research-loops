---
name: rloop-research-loop
description: Scope a scientist or engineer's first research contract. Use this when asked to start a research loop, turn a question into an experiment, or work out what data and evaluator are needed.
---

# Scope the first loop

Work with the scientist's or engineer's own coding agent operating rloop.
These skills are not injected into pilot workers.

Ask for the question, available data and rights, existing code, compute limits,
a measurable outcome and a result that would disprove the hypothesis.
Separate available material from assumptions so the first test can be checked.

Only `planted-signal` is executable today: `Contract.name` is
`Literal["planted-signal"]`. It is a known-answer sanity check.
Changing its question does not turn it into the user's real experiment.
Use `rloop init PROJECT` to learn the offline scaffold, then read
`contract.json` and `.rloop/report.md` before choosing further work.

For a real problem, scope the licensed inputs, public/private split, contract
schema, candidate format, evaluator and independent verifier, baselines,
falsifier, limits and stop rule. Record gaps for Phase 4b; the current CLI
cannot execute that contract. Live work also needs its own owner authorization.

Follow the [GUIDE](../../docs/GUIDE.md) for the executable offline path.
Consult [DESIGN](../../docs/DESIGN.md) for contract boundaries and
[LESSONS](../../docs/LESSONS.md) before promising a result.
