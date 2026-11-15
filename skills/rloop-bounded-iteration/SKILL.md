---
name: rloop-bounded-iteration
description: Run a bounded prediction-test-review cycle. Use this when asked to iterate, try the next experiment, improve a result, or decide the cheapest informative next step.
---

# Bound the next iteration

Use the scientist's or engineer's own agent; this is not a worker prompt.
Read the current contract, report and remaining allowance before proposing work.
State the prediction, its falsifier and the cheapest informative action.
Choose a stop rule before seeing the next result so failure remains useful.

Use `rloop status PROJECT` to inspect saved outcomes.
If changing supported contract fields before the final gate, edit
`contract.json`, then use `rloop plan PROJECT --reason "Explain the amendment"`.
A reason records the comparison boundary; it does not renew the shared budget.
Use `rloop run PROJECT --backend fake` for the offline campaign.
Inspect negative and failed attempts as well as supported outcomes.
Use `rloop resume PROJECT` only to reconcile saved work, not to dispatch retries.

After reviewing the evidence, choose keep, revise or stop, with a reason.
A final ticket seals the campaign; do not plan around repeated holdout access.
Only the planted-signal contract executes today; real tasks need Phase 4b.

See the [GUIDE](../../docs/GUIDE.md), [DESIGN](../../docs/DESIGN.md)
and [LESSONS](../../docs/LESSONS.md) for limits and evidence handling.
