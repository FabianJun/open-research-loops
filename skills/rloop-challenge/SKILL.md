---
name: rloop-challenge
description: Preserve contradictory evidence and an explicit resolution. Use this when a result contradicts a claim, a headline looks overstated, or a reviewer asks to challenge a finding.
---

# Challenge without rewriting history

Use the scientist's or engineer's own agent to identify the target claim,
its exact scope, the contradictory evidence and the next discriminating check.
Record artifact paths and hashes so another reader can inspect the objection.

Use `rloop report PROJECT --check` and `rloop self-assess PROJECT`
to separate report drift from a scientific disagreement.
Preserve the original statement and evidence; append the challenge and a
linked resolution rather than replacing inconvenient history.
A resolution should say which evidence changed the conclusion and what remains
uncertain. Negative outcomes need not be technical failures.

Challenge and resolution operations currently exist in the coordinator's Python
repository API; there is no challenge CLI command. Do not write the database
directly or pretend a prose note changes claim state. If a trusted coordinator
integration is unavailable, hand off the proposed record for human review.

See [DESIGN](../../docs/DESIGN.md) for challenge semantics,
[GUIDE](../../docs/GUIDE.md) for checks and
[LESSONS](../../docs/LESSONS.md) for evidence boundaries.
