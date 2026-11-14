# Requirements and acceptance trace

Checkpoint A approved 2026-11-14; [DECISIONS.md](DECISIONS.md) governs build order and scope.
This is the full acceptance inventory, not a claim that every feature is implemented. Phase 2 starts with the thin offline slice; tables are added only with consumers. See the session status record for executed checks.

Source keys:

- **M**: the user-supplied `START-PROMPT-open-research-loops.md`, prompt below its first horizontal rule; sections 1–8 and integrity items 1–11.
- **T**: user-owned toolkit paths under `skills/research-loop/` unless prefixed `docs/`; hashes are in [phase0-sources.json](phase0-sources.json).
- **L01–L11 / E03–E16**: mechanism and pinned assessment-file references in [LESSONS.md](LESSONS.md#patterns-and-failure-modes).
- **A**: the project owner's approved checkpoint-A decisions in [DECISIONS.md](DECISIONS.md).
- **P**: primary documents, repository licenses and exact version evidence in [PRIOR-ART.md](PRIOR-ART.md).

Each requirement has an implementation location in [DESIGN.md](DESIGN.md) and an observable acceptance check.
Phase 1-2 are authorized now; Phase 3, 3b, 4 and 5 require later work. Schema inventory is a ceiling; repository code/tests are preferred over unnecessary tables.

| ID | Requirement | Source | Design location | Acceptance / phase |
|---|---|---|---|---|
| R01 | Vendor-neutral Python 3.12+ package `research_loops`, CLI `rloop`; uv/Pydantic/Typer/pytest, no ORM/web/queue/Postgres implementation. | M §3–4 | Architecture | Core import works without vendor extras; fresh-clone offline command on Windows/Linux; 1–2, 5. |
| R02 | One `AgentBackend.run(contract, workspace, limits)` port, fake and two required real adapters. | M §4; T `references/models.md`; P SDK docs | Ports; Worker tools and backend equivalence | Identical port contract cases across fake/OpenAI/Claude; live cases explicitly opt-in and skipped without keys; 2–3, 5. |
| R03 | Optional SDK extras and per-task backend selection, including mixed-backend projects. | M §4 | Worker tools and backend equivalence | Resolve/install base, each extra and both; mixed fake/stub runs share one state; 1, 3. |
| R04 | One MCP tool implementation; direct wrappers only where MCP is unavailable. | M §4; P MCP/SDK docs | Worker tools and backend equivalence | Same service/schema/errors via direct fake and stdio; run scope cannot be changed by caller; 3. |
| R05 | Seven source skill folders/frontmatter use `rloop-` prefixes; no aliases/wrappers. Link installer refuses collisions; explicit SDK text injection. | M §4, §5 phase 4; P Skills | Skills, guide and command surface | Validate frontmatter, relative references and injected hashes; test symlink/junction collision without overwriting existing skills; 4. |
| R06 | Coordinator alone writes DB; workers use private outboxes and structured reports. | M §4; T `assets/schema.sql`, `references/state.md`, `references/execution.md` | Database schema; Import and artifact durability | Two coordinators cannot acquire project lock; worker tool service has no DB handle; 2–3. |
| R07 | WAL SQLite, per-connection foreign keys, numbered/checksummed migrations behind repository interface. | M §4; T `assets/schema.sql`, `references/state.md` | Database schema and persistence | Migration/reopen round trip; dangling FK and changed migration checksum rejected; 2. |
| R08 | Model project/budget/task/agent/run/artifact/decision/event semantics; add only tables used by implemented features. Claims/challenges first-class when implemented. | M §4; T `assets/schema.sql`, `references/evidence.md` | Domain and contracts; Database schema | Import linked run/evidence/claim/challenge/resolution and query intact history; 2. |
| R09 | Separate execution, scientific outcome and verification statuses. | M §4; T `references/state.md`; L03, E11 | Domain and contracts | A completed negative result is checked; timeout is never supported; illegal transitions refused; 2. |
| R10 | Evaluator is deterministic plain code, versioned/hashed, coordinator-run in protected separate process. LLM judgment is supplementary only. | M §4; T `references/validation.md`; L09, E04 | Evaluator protection; Ports | Known wrong/empty/nonfinite/timed-out evaluation is rejected; worker cannot select or edit evaluator; 2, 5. |
| R11 | Sandbox port: none refuses candidate code; container uses configurable Docker/Podman CLI, OCI Containerfile/digest, host agent/keys and stdio MCP-only tools. Enforce mounts, offline/nonroot/read-only/capability/resource policy; separate candidate evaluation container; shared-kernel threat model. | M §4; T `references/execution.md`; L02, E12 | Evaluator protection and information flow | Probe forbidden read/write, network and cleanup; missing runtime/failure blocks. All backends share isolation tests; Linux CI/local container tests, explicit Windows CI skip. Phase 3b after shared SDK contract tests; code example deferred. A4. |
| R12 | Bounded asyncio worker pool, isolated workspace per worker and bounded evaluator capacity. | M §4; T `references/execution.md` | Scheduler, limits and recovery | Four workers overlap without collisions, lost reports or corrupt records; no fifth beyond capacity; 2, 5. |
| R13 | Ideation, independent hypotheses, best-of-N and independent re-check fan-out patterns. | M §4; L08; T `references/iteration.md` | Scheduler pattern table | Exercise four patterns with deterministic workers, dependencies and retained kill/selection reasons; 2, 5. |
| R14 | Reserve shared cost/time/attempt allowance before work; reconcile afterward. | M §4, §6; T `references/state.md`, `references/execution.md` | Scheduler, limits and recovery | Racing dispatch cannot oversubscribe; duplicate imports do not charge twice; unknown interrupted costs keep reservations; 2, 5. |
| R15 | Runner enforces deadline, attempts and process-tree termination; no hidden unbudgeted SDK agents. | M §4; T `references/iteration.md` | Scheduler, limits and recovery | Worker and grandchild stopped on timeout on both OSes; all retries count; process failure is visible; 2–3, 5. |
| R16 | Evidence gate reads copied artifact bytes, verifies hash and evaluator verdict before experimental claim promotion. | M §4; T `references/evidence.md`; L03 | Import and artifact durability; Domain | Missing, altered, cross-run and incomplete artifacts cannot promote; successful exit alone is insufficient; 2, 5. |
| R17 | Contradictions and corrections append challenges/resolutions/superseding claims. | M §4; T `references/evidence.md`; plenty-of-room challenge records | Database schema; Domain | Original claim/evidence retained after challenge; current report shows contested status and resolution provenance; 2, 5. |
| R18 | Resume reconciles processes/outboxes/reservations before new dispatch. | M §4; T `references/state.md`, `references/iteration.md` | Scheduler, limits and recovery | Kill worker/coordinator at dispatch/import boundaries; mark dead worker interrupted; preserve completed work; reused PID and unknown liveness do not trigger blind reruns; 2, 5. |
| R19 | Idempotent imports: same report is a no-op, conflicting same-ID content rejected; selection by ID, never mtime. | M §4, phase-5 tests; T helper gap; L03, E04 | Import and artifact durability | Import twice and compare rows/events/revision/cost; modify only mtimes and get identical selection; 2, 5. |
| R20 | Append-only JSONL export remains reviewable in Git while DB is authoritative. | M §4, §4 closing paragraph; Cheiron idea only | Reports, grounding and export | Export twice is byte-identical; new events append only; divergent prefix and torn tail diagnosed; 2, 5. |
| R21 | Static HTML cockpit/report and every headline number derived from DB evidence. | M §4; T `references/handoff.md`; L06, E07 | Reports, grounding and export | Numeric assertions require evaluation/metric/unit binding; current challenges shown; static render has no service dependency; 2, 4–5. |
| R22 / I01 | Immutable pre-registration and per-iteration prediction before execution; amendments flag comparisons. | M integrity 1; L01; E05, E06, E08 | Domain; Evaluator protection; Database schema | Missing registration/prediction prevents start; UPDATE/DELETE fail; new version retains old and marks affected comparison; 2, 5. |
| R23 / I02 | Enforced information barrier and one-use final split; no held-out label/score in worker context. | M integrity 2; L02; E03, E05, E12, E15 | Evaluator protection and information flow | Canary/provenance leakage tests over prompts, tool results/errors and resume; second `--final` refused, including after crash or changed evaluator; 2–3, 5. |
| R24 / I03 | Complete content-addressed run manifest with candidate/code, prompt, transcript ref, raw per-example outputs, metrics, seed, inputs, version and cost. | M integrity 3; L03; E04, E06, E10, E11, E13, E15, E16 | Domain; Import and artifact durability | Manifest completeness/hash validation gates promotion; missing provider transcript access marked honestly; 2–3, 5. |
| R25 / I04 | Contract fields for controls, null/random baseline and base rate; flag constant targets/easy controls. | M integrity 4; L04; E04, E06, E08, E09, E12, E16 | Domain; Pilot; Recommended first example | Degenerate target or failed positive/negative control blocks pilot gate; baseline and control artifacts appear in report; 2, 5. |
| R26 / I05 | Count all observable variants, including abandoned ones; record seeds, keep margin and intervals. | M integrity 5; L05; E03, E06, E15 | Domain; Scheduler; Example | Proposal/execution/retry ledger reconciles complete denominators; report cannot omit failed attempts or required intervals; 2, 5. |
| R27 / I06 | Promoted evidence requires independent recomputation; CI regenerates report and fails on diff. | M integrity 6; L06; E04, E07, E09, E13, E16 | Scheduler patterns; Reports; Final attempt | Separate code path/check provenance required for independent status; second model alone fails; tampered committed report makes CI fail; 2, 5. |
| R28 / I07 | Ground quotes/numbers; validate/retry structured output and count failures; tag statements. | M integrity 7; L07; E07, E10, E13, E16 | Domain; Reports, grounding and export | Non-substring quote and wrong bound number fail; invalid schema is retried only within limits and stays counted; tags enum enforced; 2–3, 5. |
| R29 / I08 | Ideas ranked/killed in logged loop; retrieval failure is explicit, not silently model memory. | M integrity 8; L08; E05, E06 | Tools; Scheduler patterns; Skills | Fake retrieval failure yields failure event and hypothesis-only output; killed ideas have reason/evidence; 2–4. |
| R30 / I09 | Protected specs/tests/hash anchors; human-authorized new versions only. | M integrity 9; L09; E04 | Evaluator protection and information flow | Edit spec and hash together without decision: preflight/CI rejects; authorized amendment preserves history and comparison flags; 2, 5. |
| R31 / I10 | Budget-gated pilot before scaled fan-out. | M integrity 10; L10; E10, E11 | Scheduler, limits and recovery | Failed/incomplete pilot prevents fan-out even if workers/budget remain; 2, 5. |
| R32 / I11 | Per-source/dataset license metadata and repository-license self-assessment. | M integrity 11; L11; assessment index | Domain; Skills; P reuse boundary | Unknown/restricted redistribution visibly blocks public-ready verdict; mismatched/missing root license is reported; 4–5. |
| R33 | One cheap known-answer example, offline and both real providers, fixed splits/control/baseline. | M §5 phase 5; L04 | Recommended first example | Fresh-clone fake command exercises failures and a supported simulated result; each required live backend runs same schema when explicitly funded; 5. |
| R34 | Scientist/engineer guide and seven short skills; honest final self-assessment. | M §1, §5 phases 4–5; event judge skill | Skills, guide and command surface | Follow guide from empty project; inspect evidence-backed rubric and unresolved gaps without assuming positive science; 4–5. |
| R35 | Local Git from start, one commit per finished step; no remote creation/push before C. | M §6–7 | Architecture decisions; Checkpoint A | Local history shows Phase 0 steps; `git remote -v` empty; future destination decision required; all phases. |
| R36 | No spending until B; real-provider tests require explicit model/cap instruction. | M §6–7 | Limits; Checkpoint A | Live-test opt-in and project authorization both required; environment key alone does not enable a call; 1–5. |
| R37 | Secrets only from environment; `.env.example`; no personal toolkit material. | M §2, §6 | Architecture; Worker capabilities; P scope | Ignore credential files; sanitized environment/transcripts/exports; tracked-file review for personal paths and assets; 1–5. |
| R38 | Compatible code reuse with notices; AGPL ideas only. | M §2–6; P license review | Architecture decisions; P reuse table | Source inventory and notices identify actual copied files; no AGPL-derived code/skill text; all phases. |
| R39 | Cross-platform path and subprocess behavior; Linux and Windows CI. | M §4, §8; E08 hard-coded path lesson | Worker tools; Scheduler; Skills | Fresh environment matrix with spaces/non-ASCII paths, worktree, junction, process cleanup and recovery cases; 1–5. |
| R40 | CLI init/plan/run/status/resume/report/export plus self-assess workflow. | M §5 phases 2, 4 | Skills, guide and command surface | CLI smoke paths exercised offline; invalid final/recovery states fail visibly; 2, 4–5. |
| R41 | Apache-2.0 code, CC BY 4.0 docs, factual AGENTS/CLAUDE pointer and CI scaffold. | M §5 phase 1; event `CLAUDE.md` | Architecture decisions; Skills | Root license files and split agree with docs; instructions avoid duplicating source; CI exists for both OSes; 1. |
| R42 | Short docs/instructions, no personal toolkit clone or paper/hosted platform expansion. | M §1, §6; T `references/sources.md`; event `CLAUDE.md` | Architecture; Skills; L simplification | Review scope and agent instructions at handoff; disclose optional/unimplemented features; all phases. |
| R43 | Record A; finish Phase 1-2 only, vertical slice then individual integrity checks; stop before Phase 3. | A1-A6; session scope | Approved delivery order and scope | Full local Windows and disposable Linux suite; Linux environment outside mount; exact results and next three steps. No WSL change, provider calls or remote. |

## Phase-5 test coverage index

The eleven explicit test bullets in M §5 map as follows, in their original order:

| Mandated check | Requirement IDs |
|---|---|
| Wrong result, empty output and timeout rejected | R09–R10, R15–R16 |
| Pre-registration before start; amendments flagged | R22, R30 |
| Final split used once | R23 |
| No held-out data in prompts | R23–R24 |
| Duplicate import no-op; ID selection | R19 |
| Four workers, intact records, every variant counted | R12–R14, R26 |
| Limits and failed-pilot gate | R14–R15, R31 |
| Killed worker/resume, no completed rerun | R18 |
| Quote and report-number grounding | R21, R28 |
| Report regeneration matches committed copy | R27 |
| Both real adapters share contract tests; skip without keys | R02, R36 |

Phase 0 checks are documented in the final handoff; they do not satisfy these runtime tests.
No design decision at checkpoint A substitutes for proof in phases 2–5.

A2: install `research-loops`; never depend on PyPI `rloop`; mention the unrelated package once in README. A5 defers optional CLI adapters. A4 container implementation is Phase 3b, not Phase 2.
