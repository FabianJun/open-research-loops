# Requirements and acceptance trace

Checkpoint A approved 2026-11-14; [DECISIONS.md](DECISIONS.md) governs build order and scope.
This is the full acceptance inventory, not a claim that every feature is implemented. Phase 2 starts with the thin offline slice; tables are added only with consumers. See the session status record for executed checks.
Phase 1-2 are now delivered; see [PHASE-2-STATUS.md](PHASE-2-STATUS.md) for exact verification and the remaining scope.

Source keys:

- **M**: the user-supplied `START-PROMPT-open-research-loops.md`, prompt below its first horizontal rule; sections 1–8 and integrity items 1–11.
- **T**: user-owned toolkit paths under `skills/research-loop/` unless prefixed `docs/`; hashes are in [phase0-sources.json](phase0-sources.json).
- **L01–L11 / E03–E16**: mechanism and pinned assessment-file references in [LESSONS.md](LESSONS.md#patterns-and-failure-modes).
- **A**: the project owner's approved checkpoint-A decisions in [DECISIONS.md](DECISIONS.md).
- **P**: primary documents, repository licenses and exact version evidence in [PRIOR-ART.md](PRIOR-ART.md).

Each requirement has an implementation location in [DESIGN.md](DESIGN.md) and an observable acceptance check.
Phase 1-3b are complete. This delivery prepares checkpoint B offline, then stops before real sign-in, provider requests or project authorization creation. Phase 4-5 remain later work. Schema inventory is a ceiling; repository code/tests are preferred over unnecessary tables.

| ID | Requirement | Source | Design location | Acceptance / phase |
|---|---|---|---|---|
| R01 | Vendor-neutral Python 3.12+ package `research_loops`, CLI `rloop`; uv/Pydantic/Typer/pytest, no ORM/web/queue/Postgres implementation. | M §3–4 | Architecture | Core import works without vendor extras; fresh-clone offline command on Windows/Linux; 1–2, 5. |
| R02 | One `AgentBackend.run(contract, workspace, limits)` port, fake and two required real adapters. | M §4; T `references/models.md`; P SDK docs | Ports; Worker tools and backend equivalence | Identical offline port contract cases across fake/OpenAI/Claude; live acceptance needs explicit checkpoint-B authorization; 2–3, 5. |
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
| R35 | One commit per finished step; ordinary green pushes to the existing private origin are authorized. No force-push or pushed-history rewrite. | M §6–7; subsequent owner authorization | Decisions; delivery record | Inspect CI after each push. Preserve concurrent work; no repository settings/secrets/releases/tags changes or public publication before C. |
| R36 | No provider requests before B; exact provider/model/auth-mode/run-limit approval; optional USD cap only for API-key mode. | Owner checkpoint-B preparation decisions | Checkpoint-B auth and run policy | Keys never authorize runs or override subscriptions. Absent approval, exhausted limits and unlisted ChatGPT models refuse. No fallback; offline OAuth/API/SDK seams only. |
| R37 | Credentials remain host-only. Explicit API keys or protected user-scoped OAuth storage; no personal toolkit material. | M §2, §6; checkpoint-B auth decisions | Architecture; auth and worker capabilities | Never inspect other applications' credential files. Own token storage outside repo/project, restrictive permissions, atomic rotation; no secrets in MCP environment, logs or exports. |
| R38 | Compatible code reuse with notices; AGPL ideas only. | M §2–6; P license review | Architecture decisions; P reuse table | Source inventory and notices identify actual copied files; no AGPL-derived code/skill text; all phases. |
| R39 | Cross-platform path and subprocess behavior; Linux and Windows CI. | M §4, §8; E08 hard-coded path lesson | Worker tools; Scheduler; Skills | Fresh environment matrix with spaces/non-ASCII paths, worktree, junction, process cleanup and recovery cases; 1–5. |
| R40 | CLI init/plan/run/status/resume/report/export plus self-assess workflow. | M §5 phases 2, 4 | Skills, guide and command surface | CLI smoke paths exercised offline; invalid final/recovery states fail visibly; 2, 4–5. |
| R41 | Apache-2.0 code, CC BY 4.0 docs, factual AGENTS/CLAUDE pointer and CI scaffold. | M §5 phase 1; event `CLAUDE.md` | Architecture decisions; Skills | Root license files and split agree with docs; instructions avoid duplicating source; CI exists for both OSes; 1. |
| R42 | Short docs/instructions, no personal toolkit clone or paper/hosted platform expansion. | M §1, §6; T `references/sources.md`; event `CLAUDE.md` | Architecture; Skills; L simplification | Review scope and agent instructions at handoff; disclose optional/unimplemented features; all phases. |
| R43 | A and Phase 1-3b complete; current scope is checkpoint-B preparation offline. Stop before live sign-in/inference, project approval creation and Phase 4. | A1-A6; subsequent owner authorization | Approved delivery order and scope | Full Windows/disposable Linux/CI verification with exact results and owner go instructions. No WSL change, real auth/API requests or provider calls; private-origin green pushes authorized. |

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
| Both SDK adapters share offline contract tests through SDK seams; real calls require checkpoint B | R02, R36 |

Phase 0 checks are documented in the final handoff; they do not satisfy these runtime tests.
No design decision at checkpoint A substitutes for proof in phases 2–5.

## Implemented offline integrity evidence

| Mechanism | Executable evidence |
|---|---|
| I01 registration/prediction | `test_registration_is_immutable_and_required`, `test_amendment_is_explicit_and_retains_history`; DB triggers and explicit amendments. |
| I02 information barrier/final | `test_final_labels_are_not_reopened_before_ticket`, `test_public_projection_has_no_private_fields`, final/crash/receipt/reused-PID tests; `test_mcp.py`, shared SDK and container isolation tests now add Phase 3/3b evidence. |
| I03 complete records | `test_import_is_true_noop_and_seals_evidence`, `test_tampered_artifact_never_imports`, full slice artifact/claim counts; raw outputs, transcripts, source hash, inputs, cost and seeds saved. |
| I04 controls/baselines | `test_wrong_and_known_correct_candidates`, `test_failed_control_blocks_all_worker_dispatch`, `test_splits_are_disjoint_tuples_and_not_constant`; random-expression arm uses the same candidate grammar. |
| I05 selection | Full 48-run slice, attempt/budget gates, frozen seeds/margin, deterministic descriptive bootstrap and method fingerprint. Fake oracle comparison is simulated, not scientific efficacy evidence. |
| I06 independent check/report gate | `test_independent_verifier_catches_plausible_but_wrong_outputs`; separate stack/rational implementation; committed report comparison script in both CI jobs. |
| I07 grounding/schema | `test_grounding_and_tags`, nonfinite/process-output rejection, strict unknown-field models, report numeric bindings and raw artifact checks. No LLM retry policy is implemented before SDK adapters. |
| I08 ideation/literature | `test_ideas_rank_and_die_on_paper_and_retrieval_fails_loudly`; logged API helpers, no network retriever or interactive planner. |
| I09 protected evaluator | Anchor verification, `test_anchor_and_spec_cannot_change_together_without_prior_decision`, trusted-base CI script. Initial anchor and future human decisions need owner review. |
| I10 pilot | `test_deadline_and_pilot_gate`, `test_failed_control_blocks_all_worker_dispatch`. |
| I11 licenses | `test_license_metadata_and_repository_check`; synthetic contract CC0, code/docs root license checks. Full self-assess skill remains Phase 4. |

R02-R04: MCP parity and both optional SDK adapters have offline SDK-seam contract tests, including effective tools and key-free server environments. Live acceptance remains checkpoint-B gated, independent of keys. R05 skills remain Phase 4. R11: none/container Sandbox, digest/mount/resource policy, separate code-evaluation container and four actual probes are implemented and tested. Podman command parity is tested; actual engine verification uses Docker. R13 has four tested pattern policies; generic multi-contract/dependency planning and R21/R34's full guide/cockpit experience remain later work. R18 recovery is implemented for in-process fake workers and supervised evaluators; live SDK session recovery remains pending. R36 now requires exact owner/provider/model/auth-mode/effort/run-limit configuration and retains the offline socket guard. Historical evidence is in PHASE-3-STATUS; current evidence and go instructions are in CHECKPOINT-B-PREP.

A2: install `research-loops`; never depend on PyPI `rloop`; mention the unrelated package once in README. A5 defers optional CLI adapters. A4 container implementation is Phase 3b, not Phase 2.

## Checkpoint-B preparation evidence

The earlier Phase-3 R36 USD-only gate is superseded by exact provider/model/auth mode/effort and four run limits. Subscription cost is an estimate, never a ledger charge; unknown tokens/cost stay unknown. API-key mode requires explicit selection; an optional cap retains conservative reservations. No approval is created. `test_authorization.py` covers absent/mismatched approval, durable count/parallel limits, actual SDK turn exhaustion, wall time, rate-limit shutdown and credential-free Claude child environment. `test_openai_auth.py` covers OAuth registration, PKCE, state, cryptographic identity, returning accounts, scope refusals, protected storage, rotation/serialization and callback ordering through offline endpoints. `test_chatgpt_responses.py` drives actual SDK streaming plus MCP, checks preview request constraints, rejects unlisted models and verifies no retries/fallback on limits or interrupted streams. The socket guard remains enabled. Model choices and proposed 8/48-worker pilots still need owner go. Exact verification belongs in CHECKPOINT-B-PREP.md.
