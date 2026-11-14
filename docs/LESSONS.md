# Lessons from thirteen research-loop submissions

## Lessons from preparation

The hackathon toolkit supplied instructions, a method and a state helper; it never ran a real research problem. The missing piece was runtime, not method: no experiment runner, scheduler or provider adapters. These are facts from the supplied start prompt and toolkit, not claims of validated scientific performance.

Phase 0 review, 2026-11-14.
These are conclusions from the event's published assessments, not a fresh audit of the submission repositories or a reproduction of their science.
All thirteen assessments were read at event commit `8d8a24a3215c8900906dd5d665f04d8abde6377e`.
The assessor inspected artifacts and independently recomputed selected results without running submission code.
We likewise executed no organizer or submission code.
References below identify the assessment file; their **Claims checked**, **Strengths**, and **What would make it stronger** sections supply the detail.

## What the teams built

| Assessment | Work demonstrated | Finding or limitation that matters to this framework |
|---|---|---|
| [3-chainsentinel.md][E03] | Explainable transfer-graph rules to recover held-out laundering addresses. | Strong offline evidence and label separation; an unreachable goal was diagnosed, but eleven development variants had no committed producing script. |
| [4-plov.md][E04] | Agent-built SSH mapping and a published-mapper comparison, with live witness replay. | A second harness exposed errors; choosing verdicts by modification time admitted stale results, and the orchestrator changed both a protected spec and its hash. |
| [5-micrograph.md][E05] | A planner/reviewer loop tuning classical grain segmentation. | The real-data target was missed honestly; the planner loosened a threshold, medians hid failing images, and literature retrieval quietly became model memory. |
| [6-meowlignment.md][E06] | Experiment and ideation loops for executable reward-hacking testbeds. | Raw samples, controls, and fixed criteria supported the repository's cautious verdict; the submission dropped intervals and overstated point estimates. |
| [7-baucode.md][E07] | Construction-material rankings and a separate wall-calculation regression harness. | Assumptions were labelled and totals checked, but the issue quoted an obsolete moisture number; the two loops were unconnected. |
| [8-shift-happens.md][E08] | Calcium-reactivation methods gated by synthetic and real positive controls. | Locked answer rules and predictions preceded relevant runs; failed controls stayed failed. Verdict-rule precedence and an uncommitted verdict invocation remained gaps. |
| [9-dr-drerio.md][E09] | Supervisor/researcher cycles auditing cell-state markers, with planted-defect checks. | Separate supervisor code changed conclusions; easy defects tested wiring rather than sensitivity, and the registered configuration diverged from implementation. |
| [10-kaanom.md][E10] | A grounded interview-profiling loop alongside two other, unpublished approaches. | Verbatim quote checks and evidence tags worked; missing run/cost files and partial coverage limited reproducibility and comparison. |
| [11-metabolite-sensor-finder.md][E11] | A prompt specifying a staged protein–metabolite screening funnel. | Thoughtful pilot and recording rules were specifications without an end-to-end run; simulated workers on another branch were not a scientific result. |
| [12-science-resocialized.md][E12] | Masked psychology-replication agents and hashed reviewer handoffs. | Review panels had not run; attached agents had prompt-only isolation, truth files were public, and the intended review target was constant. |
| [13-do-llms-argue-like-humans.md][E13] | Reasoning-graph extraction, validation, and a documented extraction-method study. | The method study was supported; the submission's headline comparison pilot had no saved artifacts. Failed extraction outputs were correctly retained. |
| [15-llm-lying-detection.md][E15] | Probe-code search and a separate probe-weight-editing loop. | Family splits and keep margins were useful; raw evidence stayed in Colab, a second loop included test scores in its prompt, and one seed limited inference. Issue 14 is the same team. |
| [16-predictive-lens.md][E16] | Reproducible forecasting/backtest tools plus a checked language explanation. | CI regenerated committed backtests; other tool outputs were missing, and deterministic tools alone did not establish an agentic loop. |

## Patterns and failure modes

The following table verifies **each of the eleven integrity mechanisms** in the start prompt against the named assessments.
The proposed enforcement is a design requirement, not behavior already implemented here.

| ID / mechanism | Assessment evidence | Reusable rule |
|---|---|---|
| L01 — Pre-registration | [E08][E08]: locked answer key and pre-run prediction commits; [E05][E05]: planner-set looser target; [E06][E06]: fixed thresholds and interval rule. | Store immutable, timestamped versions of the goal, executable rule, thresholds, and each prediction before execution; link amendments and flag comparisons. |
| L02 — Information barriers | [E03][E03], [E05][E05], [E15][E15]: separated evaluation inputs; E15's later prompt leaked test scores; [E12][E12]: attached mode did not enforce the seal. | Give workers an allowlisted view. Keep final inputs and scores outside that view, spend a one-use final ticket, and scan recorded context for leaks. |
| L03 — Complete records | [E06][E06] and [E04][E04]: raw sample/query logs; [E10][E10], [E11][E11], [E13][E13], [E15][E15], [E16][E16]: absent runs or outputs; E04: stale mtime-selected verdict. | Save manifests and content hashes, including failures; select by immutable IDs. Missing artifacts block promotion. |
| L04 — Controls and baselines | [E06][E06], [E08][E08], [E04][E04], [E16][E16]: diagnostic controls; [E09][E09]: defects too easy; [E12][E12]: constant target. | Require declared baseline/control cases and base rates; fail a pilot with a degenerate target or uninformative control. |
| L05 — Selection accounting | [E03][E03]: uncommitted variants; [E15][E15]: single seed and keep margin; [E06][E06]: intervals omitted from the issue. | Count proposals, variants, retries, and abandoned attempts; report the selection protocol, seeds, keep margin, denominator, and intervals. |
| L06 — Independent verification and report gate | [E09][E09]: supervisor recomputation; [E04][E04]: second harness; [E07][E07]: stale headline; [E13][E13]: unsupported pilot; [E16][E16]: regeneration in CI. | Verify through a separate computation and render reports from database references; CI must fail on a changed committed report. |
| L07 — Grounded language | [E10][E10]: exact source substrings and labelled statements; [E13][E13]: shared validator, retries, failures counted; [E16][E16]: number checking; [E07][E07]: assumptions explicit. | Validate quotes and structured results. Render numeric assertions from typed database bindings; require a provenance tag on each report statement. |
| L08 — Logged ideation and literature | [E06][E06]: fifteen setups, ten rejected before measurement; [E05][E05]: URLs did not make memory-based notes retrieved evidence. | Persist proposals/rankings/rejections. Failed retrieval is a recorded failure; uncited ideas remain hypotheses. |
| L09 — Protected specifications | [E04][E04]: spec and protecting hash changed together. | Anchor hashes outside the worker's authority. Spec changes need a separately recorded human authorization and a new version. |
| L10 — Pilot before scale | [E10][E10]: budgeted partial run and selection effects; [E11][E11]: scaling described before a first working pilot. | Reserve a small pilot budget and require evaluator, control, evidence, and cost checks before fan-out. |
| L11 — Donation readiness | The [assessment index][INDEX] marks only micrograph, BauCode, and Shift Happens **OK**. | Record source/dataset licenses and attribution independently of the repository license; assess the actual public artifact set, including quoted text. |

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

[E03]: https://github.com/xemantic/claude-impact-lab-2026/blob/8d8a24a3215c8900906dd5d665f04d8abde6377e/assessments/3-chainsentinel.md
[E04]: https://github.com/xemantic/claude-impact-lab-2026/blob/8d8a24a3215c8900906dd5d665f04d8abde6377e/assessments/4-plov.md
[E05]: https://github.com/xemantic/claude-impact-lab-2026/blob/8d8a24a3215c8900906dd5d665f04d8abde6377e/assessments/5-micrograph.md
[E06]: https://github.com/xemantic/claude-impact-lab-2026/blob/8d8a24a3215c8900906dd5d665f04d8abde6377e/assessments/6-meowlignment.md
[E07]: https://github.com/xemantic/claude-impact-lab-2026/blob/8d8a24a3215c8900906dd5d665f04d8abde6377e/assessments/7-baucode.md
[E08]: https://github.com/xemantic/claude-impact-lab-2026/blob/8d8a24a3215c8900906dd5d665f04d8abde6377e/assessments/8-shift-happens.md
[E09]: https://github.com/xemantic/claude-impact-lab-2026/blob/8d8a24a3215c8900906dd5d665f04d8abde6377e/assessments/9-dr-drerio.md
[E10]: https://github.com/xemantic/claude-impact-lab-2026/blob/8d8a24a3215c8900906dd5d665f04d8abde6377e/assessments/10-kaanom.md
[E11]: https://github.com/xemantic/claude-impact-lab-2026/blob/8d8a24a3215c8900906dd5d665f04d8abde6377e/assessments/11-metabolite-sensor-finder.md
[E12]: https://github.com/xemantic/claude-impact-lab-2026/blob/8d8a24a3215c8900906dd5d665f04d8abde6377e/assessments/12-science-resocialized.md
[E13]: https://github.com/xemantic/claude-impact-lab-2026/blob/8d8a24a3215c8900906dd5d665f04d8abde6377e/assessments/13-do-llms-argue-like-humans.md
[E15]: https://github.com/xemantic/claude-impact-lab-2026/blob/8d8a24a3215c8900906dd5d665f04d8abde6377e/assessments/15-llm-lying-detection.md
[E16]: https://github.com/xemantic/claude-impact-lab-2026/blob/8d8a24a3215c8900906dd5d665f04d8abde6377e/assessments/16-predictive-lens.md
[INDEX]: https://github.com/xemantic/claude-impact-lab-2026/blob/8d8a24a3215c8900906dd5d665f04d8abde6377e/assessments/README.md
[CH43]: https://github.com/xemantic/plenty-of-room/blob/2fbb80f36c17cf39cfcc933b182861f219076b17/gpd/challenges/CH-0043-a-reproducibility-certificate-that-certifies-the-path.md
