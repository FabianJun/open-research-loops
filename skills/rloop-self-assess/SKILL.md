---
name: rloop-self-assess
description: Review research claims against saved evidence without giving a score. Use this before a handoff or publication, or when asked for an honest self-assessment, reproducibility review, or license check.
---

# Review evidence and open questions

Use the scientist's or engineer's own coding agent to run
`rloop self-assess PROJECT`, or `rloop self-assess PROJECT --write`
to save `.rloop/self-assessment.md`.
The deterministic offline inventory checks saved state; it dispatches no work.

Review five dimensions:
- Problem: distinguish a meaningful research question from a demonstration.
- Loop: inspect the contract, controls, bounded attempts and checking procedure.
- Evidence: trace conclusions to intact artifacts and evaluator outputs.
- Honesty: account for negatives, failures, uncertainty and scope.
- Reproducibility: inspect instructions, report drift and the export chain.

Keep license review and potential impact as separate discussions.
Decide whether the evaluator fits the claim, who benefits and what risks remain.
These judgments stay open; do not convert them into scores or automatic passes.
Planted-signal is a known-answer sanity check, including when models ran live.
A blocker gives `public-ready: no`; otherwise it remains
`public-ready: needs human review`, never an automatic yes.

Rubric adapted in our own words from xemantic's claude-impact-lab-2026
judge-submissions skill (Apache-2.0 code, CC BY 4.0 text); repository credits
identify the pinned source. No assessment bodies are reproduced.
See [DESIGN](../../docs/DESIGN.md), [GUIDE](../../docs/GUIDE.md)
and [LESSONS](../../docs/LESSONS.md) for the executable scope.

The lines from "Review five dimensions" through "Keep license review and
potential impact as separate discussions." are licensed CC BY 4.0; the rest
of this file is licensed under Apache-2.0.
