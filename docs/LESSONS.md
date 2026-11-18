# Lessons from thirteen research-loop submissions

## Lessons from preparation

The hackathon toolkit supplied instructions, a method and a state helper; it never ran a real research problem. The missing piece was runtime, not method: no experiment runner, scheduler or provider adapters. These are facts from the supplied start prompt and toolkit, not claims of validated scientific performance.

Phase 0 review, 2026-11-14.
These are conclusions from the event's published assessments, not a fresh audit of the submission repositories or a reproduction of their science.
All thirteen assessments were read at event commit `8d8a24a3215c8900906dd5d665f04d8abde6377e`.
The assessor inspected artifacts and independently recomputed selected results without running submission code.
We likewise executed no organizer or submission code.
This page turns those assessments into general patterns. It names no team or project; "n of 13" counts the assessments that showed a pattern.
The source is the event's [assessment index][INDEX] at that commit; each assessment's **Claims checked**, **Strengths**, and **What would make it stronger** sections supply the detail.
A reader of those assessments can still trace a single finding back to its submission; this page only avoids naming or describing one.
The event is named in the README section [Why this exists](../README.md#why-this-exists).

## What the submissions built

| Shape of the work | n of 13 |
|---|---|
| One agent loop with separate roles or stages, for example planning and review, or ideation and experiment stages | 4 |
| Two or more loops or approaches in one submission, not connected to each other or not all published | 3 |
| Methods or pipelines checked against held-out labels, positive controls, a validator, a second harness or a published tool | 4 |
| Tools or specifications without a full agent loop: deterministic tools with a language layer, or a specified pipeline without an end-to-end run | 2 |

## What held up

| Pattern | n of 13 | What it means for this framework |
|---|---|---|
| Answer rules, thresholds or predictions were locked before the relevant runs. Seen: a locked answer key and pre-run predictions; fixed thresholds with an interval rule. | 2 | Lock the rule before any result exists. |
| Evaluation inputs or labels were kept apart from development; one submission also used grouped splits and a keep margin. | 3 | Separation works when it is enforced, not only described. |
| One submission diagnosed why a goal was unreachable; another documented a method study that held up. | 2 | Explaining why a target fails, or how a method behaves, is a result too. |
| The raw record was kept. Seen: raw samples, controls and fixed criteria behind a cautious verdict; complete query logs. | 2 | Keep the raw record; it is what makes a verdict checkable. |
| Negative results were kept. Seen: a missed target reported honestly; failed controls kept as failed; failed outputs retained. | 3 | Negative results belong in the record and the report. |
| Verbatim quote checks, evidence tags, a shared validator, number checks, labelled assumptions and checked totals kept language grounded. | 4 | Ground every statement in a checked source or a typed result. |
| A separate computation changed or confirmed conclusions: separate review code, a second harness, or CI that regenerated committed outputs. | 3 | Independent verification finds errors the producing loop misses. |

## What broke

| Pattern | n of 13 | What it means for this framework |
|---|---|---|
| Results had no committed producing script or no saved artifacts: development variants, run and cost files, a headline pilot, raw evidence left in a hosted notebook, other tool outputs. | 5 | A result without its artifacts cannot be promoted. |
| The agent changed its own guardrails: a planner loosened a threshold, an orchestrator changed a protected spec together with its hash. | 2 | Guardrails sit outside the worker's authority. |
| Information reached the worker's view: a later prompt included test scores; truth files were public and isolation was prompt-only. | 2 | Isolation must be enforced by the runtime, not by a prompt. |
| A verdict was chosen by file modification time and admitted stale results. | 1 | Select by immutable IDs, never by mutable file state. |
| Even with locked rules, the precedence between verdict rules was open and the verdict invocation was not committed. | 1 | The verdict step itself must be specified and recorded. |
| Checks were too weak: planted defects tested wiring rather than sensitivity, a review target was constant, medians hid failing cases, and a registered configuration diverged from the implementation. | 3 | A control must be able to fail, and the run must match what was registered. |
| Selection and uncertainty were under-reported: a single seed, dropped intervals, overstated point estimates. | 2 | Report seeds, denominators and intervals with every number. |
| The submission text drifted from the repository: an obsolete number was quoted, intervals were dropped, a headline comparison had no saved artifacts. | 3 | Render reports from the record, so text cannot drift from evidence. |
| The documented run command wrote its cache to a hard-coded, machine-specific path and would fail on another machine; the tests bypassed the cache, so CI did not catch it. | 1 | Default to paths inside the run folder or the temp folder, and test the documented command as written. |
| Literature retrieval quietly became model memory. | 1 | A failed retrieval is a recorded failure, not a citation. |
| Plans or simulations stood in for runs: careful pilot and recording rules without an end-to-end run, simulated workers on another branch, review panels that had not run, deterministic tools without an agentic loop. | 3 | Good rules are a start; only an executed run counts as a result. |
| Several loops in one submission did not work as one. Seen: loops left unconnected; loops that covered only part of the cases, which limited comparison. | 2 | One contract per question; compare only like with like. |

## Patterns and failure modes

The following table verifies **each of the eleven integrity mechanisms** in the start prompt against the assessments.
The proposed enforcement is a design requirement, not behavior already implemented here.

| ID / mechanism | What the assessments showed | Reusable rule |
|---|---|---|
| L01 — Pre-registration | A locked answer key and pre-run prediction commits (1 of 13); a planner-set looser target (1 of 13); fixed thresholds and an interval rule (1 of 13). | Store immutable, timestamped versions of the goal, executable rule, thresholds, and each prediction before execution; link amendments and flag comparisons. |
| L02 — Information barriers | Separated evaluation inputs (3 of 13), one of which later leaked test scores into a prompt; an attached mode that did not enforce the seal (1 of 13). | Give workers an allowlisted view. Keep final inputs and scores outside that view, spend a one-use final ticket, and scan recorded context for leaks. |
| L03 — Complete records | Raw sample and query logs (2 of 13); absent runs or outputs (5 of 13, not the same five as the first row under "What broke"); a stale verdict selected by modification time (1 of 13). | Save manifests and content hashes, including failures; select by immutable IDs. Missing artifacts block promotion. |
| L04 — Controls and baselines | Diagnostic controls (4 of 13); planted defects too easy to catch (1 of 13); a constant review target (1 of 13). | Require declared baseline/control cases and base rates; fail a pilot with a degenerate target or uninformative control. |
| L05 — Selection accounting | Uncommitted variants (1 of 13); a single seed with a keep margin (1 of 13); intervals omitted from the submission text (1 of 13). | Count proposals, variants, retries, and abandoned attempts; report the selection protocol, seeds, keep margin, denominator, and intervals. |
| L06 — Independent verification and report gate | Recomputation by a separate role, a second harness, and regeneration in CI (1 of 13 each); a stale headline and an unsupported pilot (1 of 13 each). | Verify through a separate computation and render reports from database references; CI must fail on a changed committed report. |
| L07 — Grounded language | Exact source substrings and labelled statements; a shared validator with retries and counted failures; number checking; explicit assumptions (1 of 13 each). | Validate quotes and structured results. Render numeric assertions from typed database bindings; require a provenance tag on each report statement. |
| L08 — Logged ideation and literature | Most proposed setups rejected before measurement (1 of 13); URLs that did not make memory-based notes retrieved evidence (1 of 13). | Persist proposals/rankings/rejections. Failed retrieval is a recorded failure; uncited ideas remain hypotheses. |
| L09 — Protected specifications | A spec and its protecting hash changed together (1 of 13). | Anchor hashes outside the worker's authority. Spec changes need a separately recorded human authorization and a new version. |
| L10 — Pilot before scale | A budgeted partial run with selection effects (1 of 13); scaling described before a first working pilot (1 of 13). | Reserve a small pilot budget and require evaluator, control, evidence, and cost checks before fan-out. |
| L11 — Donation readiness | The [assessment index][INDEX] marks three of thirteen submissions **OK**. | Record source/dataset licenses and attribution independently of the repository license; assess the actual public artifact set, including quoted text. |

These examples support engineering choices, not a causal estimate that a database would have improved the teams' science.
The reviewable files made the assessments possible; a database must preserve that visibility through export.
Reproducibility and scientific validity also differ: identical outputs can still use the wrong assumptions or excessive reported precision.
The organizer's [challenge CH-0043][CH43] illustrates that distinction.

## What the personal toolkit already covers

Paths here are relative to the user-owned `ClaudeCodeScienceHackathon` source, not this repository.
No personal profile, checklist answers, logistics, or event budget has been imported.

| Source file | Retain | Gap to close |
|---|---|---|
| `skills/research-loop/references/iteration.md` | Falsifiable bounded work, cheapest informative check, limited repairs, checkpoint and continue. | Actual deadlines, attempt accounting, and scheduling. |
| `references/evidence.md` under that skill | Inspect saved outputs before reuse; retain contradictions, provenance, units, and scope. | Claims/challenges are currently artifact conventions; the helper permits upserts rather than immutable evidence transactions. |
| `references/state.md`, `assets/schema.sql` | Eight base tables, separate execution/scientific/verification fields, one coordinator writer, budget reservations and restart reconciliation. | WAL initialization, migrations, enforced import deduplication, normalized claims/challenges, runner recovery. |
| `references/validation.md`, `references/execution.md` | Candidate/evaluator separation; worktrees and environments are not sandboxes; scientific and technical checks differ. | A protected evaluator process, actual worker capabilities, process-tree termination, and enforceable budgets. |
| `scripts/workspace.py` inside the skill | Parameterized SQL, `BEGIN IMMEDIATE`, versioned feedback, strict JSON loading, and derived HTML. | `record()` updates existing IDs and appends another event on every call; it is not the required idempotent WorkerReport importer. No scheduler or provider adapter exists. |
| `docs/WORKFLOW.md`, `references/handoff.md`, `references/sources.md` | Scientist judgment, a complete first trial, evidence-linked handoff, and explicit untried status. | A runnable example proving the workflow rather than describing it. |

## Simplify for a one-day team

This is a design judgment, not a measured assessment of the toolkit's usability.
Keep a short intake that produces one contract; make the static report a view of runs and decisions.
Remove the personal preparation system, browser feedback protocol, event funding assumptions, and mandatory multi-role ceremony from the generic runtime.
Keep domain-specific numerical checks in evaluators rather than requiring the same five checks for every discipline.
Do not adopt the organizer's unconditional pushes, per-iteration session endings, or universal test-first policy.
Use focused regression checks for the integrity boundaries and spend the remaining day on a real, bounded experiment.

[INDEX]: https://github.com/xemantic/claude-impact-lab-2026/blob/8d8a24a3215c8900906dd5d665f04d8abde6377e/assessments/README.md
[CH43]: https://github.com/xemantic/plenty-of-room/blob/2fbb80f36c17cf39cfcc933b182861f219076b17/gpd/challenges/CH-0043-a-reproducibility-certificate-that-certifies-the-path.md
