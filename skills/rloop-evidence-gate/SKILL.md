---
name: rloop-evidence-gate
description: Check whether a claim is ready to promote from saved evidence. Use this when asked to verify a finding, audit evidence, check a verdict, or justify a headline number.
---

# Inspect the evidence gate

Use the scientist's or engineer's own agent to review coordinator-owned evidence.
Start with `rloop report PROJECT --check` and
`rloop self-assess PROJECT`. Preserve failures for diagnosis.

Trace each claim to the registration, imported candidate, artifact hash,
raw evaluator verdict and independent arithmetic check. A worker's prose
or metric is not authoritative because its outbox is untrusted.
Check execution status separately from scientific outcome and verification:
a completed negative run can be checked evidence.

Use the saved report's evidence links and assessment sources to inspect objects.
Keep simulated, measured, cited and interpretive statements distinct.
Do not promote discovery claims from the known-answer planted-signal example.
The CLI has no manual claim-promotion command; do not invent one.
Self-assessment checks evidence but never certifies scientific validity.

Consult [DESIGN](../../docs/DESIGN.md) for promotion rules,
[GUIDE](../../docs/GUIDE.md) for the offline re-check and
[LESSONS](../../docs/LESSONS.md) for known limits.
