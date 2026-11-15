---
name: rloop-handoff-report
description: Prepare an evidence-linked research handoff with limits and next steps. Use this when asked to hand off, report findings, reproduce a campaign, or summarize what worked and failed.
---

# Hand off saved evidence

Use the scientist's or engineer's own coding agent to produce a reviewable
handoff from saved coordinator evidence.
Run `rloop report PROJECT --check`, `rloop export PROJECT` and
`rloop self-assess PROJECT --write`. Preserve report drift for diagnosis;
regeneration should not silently erase a discrepancy.

Link the contract hash, report, evidence objects, event export and assessment.
Include exact reproducible commands, execution statuses, negative outcomes,
technical failures, uncertainty and the next informative action.
Distinguish checked measurements from interpretation and proposed work.
Describe planted-signal as a known-answer sanity task; even live model workers
do not turn it into discovery.

Keep license and impact questions visible. A clean tool check only leaves
human review pending; it is not permission to publish or to start a live pilot.
Avoid exposing host settings or credentials in a shared handoff.

Use [GUIDE](../../docs/GUIDE.md) for commands,
[DESIGN](../../docs/DESIGN.md) for evidence/export semantics and
[LESSONS](../../docs/LESSONS.md) for limitations.
