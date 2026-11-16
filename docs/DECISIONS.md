# Decisions

## Checkpoint A — approved 2026-11-14

Authority: the project owner's checkpoint-A decisions.
This record supersedes the Phase-0 recommendations where they differ.

| ID | Decision |
|---|---|
| A1 | Architecture approved. First build the smallest offline vertical slice: registration → fake worker using tool functions → outbox/import → protected evaluator subprocess → verdict → report/export. Add integrity mechanisms individually with tests. Migrations add tables only alongside code using them. Prefer repository code and tests over extra tables; the design inventory is a ceiling. |
| A2 | Repository `open-research-loops`, distribution `research-loops`, import `research_loops`, console script `rloop`. The project owner reports the three distribution spellings available on PyPI on 2026-11-14. The unrelated PyPI `rloop` Rust asyncio package must never be a dependency; install instructions use `research-loops`, with one README notice. |
| A3 | Build `examples/planted-signal` as proposed. |
| A4 | Declarative MCP-only default; fail closed for code execution without isolation. Add a vendor-neutral `Sandbox` port in Phase 3b, after fake and both SDK adapters pass shared tests. `none` refuses candidate code execution; `container` uses configurable Docker/Podman CLI with common flags, OCI `Containerfile`, no docker-py. Agent/API keys remain on the host; only tools execute in containers through stdio MCP (`run -i` / `exec -i`). Built-in SDK tools are off. All backends pass the same isolation tests. |
| A5 | Codex and Claude Code CLI adapters deferred. |
| A6 | Prefix all seven source skill folders and frontmatter names with `rloop-`: research-loop, bounded-iteration, evidence-gate, challenge, parallel-fanout, handoff-report, self-assess. No wrapper/alias mechanism. Installer refuses differing existing targets. |

### A4 container policy and limits

Worker container: workspace read-write, public inputs read-only; no evaluator, holdout, database, or credentials. Use `--network none`, non-root user, `--read-only` root plus tmpfs, `--cap-drop ALL`, `--security-opt no-new-privileges`, pids/memory/CPU/wall-time limits. Pin the image by digest and record it per run. For code tasks, execute the candidate in a separate evaluator-side container with read-only holdout; the evaluator process never loads candidate code.

Preflight probes must demonstrate inaccessible evaluator/holdout paths, no writes outside the workspace, no network, and process-tree cleanup. Failure or missing runtime blocks execution. Containers share the host kernel: protection covers mistakes and opportunistic actions, not determined kernel exploits. gVisor `runsc` and hosted sandbox providers may be optional future adapters, never prerequisites.

Phase 3b container tests run on Linux CI and locally. Skip on GitHub Windows runners with an explicit reason (Linux containers unavailable). The project owner reports Docker Desktop 29.8.1 with WSL2 Linux engine locally; daemon availability must still be checked. A code-changing example is deferred.

### Authorized scope of this session

Phase 1: scaffold and `uv.lock`, Apache-2.0 code / CC BY 4.0 docs, factual AGENTS plus CLAUDE pointer, Linux/Windows CI.
Phase 2: offline vertical slice followed by core integrity checks without real SDKs. Stop before Phase 3. DESIGN is internal; README/GUIDE stay short.

Verify the full suite on Windows and in a disposable Linux container, using `UV_PROJECT_ENVIRONMENT` outside the mounted checkout. Do not change WSL. Record exact commands/results. No Git remote exists; GitHub CI cannot be run here.

Local commits only; no paid calls, even with API keys present; no code executed from `refs/`; AGPL ideas only; no personal toolkit data. If a technical failure survives two targeted fixes, stop and report the diagnosis.

Checkpoint B (provider/model/USD cap) and C (publication destination/licenses/files) remain pending.

## Phase 3 / 3b authorization — 2026-11-15

The project owner authorized MCP stdio parity, both optional SDK adapters tested at their own offline seams, then the A4 none/container Sandbox port. Stop after Phase 3b. Do not create checkpoint-B authorization or make any provider call.

The private `origin` repository and its noreply history rewrite are legitimate. Green local commits may be pushed with `git push origin main`; inspect CI with `gh`. No force-push, pushed-history rewrite, settings/visibility/secrets changes, releases, tags or other repositories. Public publication remains checkpoint C.

Lead with time to the first running scientific experiment. Measure the offline init-to-pilot path; no invented time target. The first scaffold remains explicitly simulated planted-signal, not a substituted evaluator for the scientist's real problem. GUIDE and skills remain Phase 4.

## Checkpoint-B preparation — 2026-11-15

The project owner approved keeping both vendor adapters and using each user's own subscriptions by default: Claude Code login and Sign in with ChatGPT token sharing for locally run open-source apps. API-key mode remains an explicit option. Credentials never authorize a run. Do not read existing credential files, perform a real sign-in, create project authorization or call providers in this delivery.

The implementation may prepare the proposed gate: owner, provider, exact model, explicit auth mode, effort, maximum worker runs, parallel workers, turns and wall time. A USD cap is optional and API-key-only. This is approval to build the offline gate, not approval of any live run or particular limits. Record token usage and SDK-reported USD as estimates; unknown stays unknown.

The proposed documentation choices are `claude-fable-5-2` at high effort and `gpt-6-astra` if listed for the signed-in ChatGPT account. `gpt-6.1-sol` requires a separate explicit project choice if Astra is unavailable; never fall back automatically. Cheaper models require explicit project configuration. Model IDs were checked against official model pages on this date. Models and limits remain configurable before go.

Proposed next: eight workers per backend first, 48 later, and cross-vendor rechecking. First example remains planted-signal, controls first, MCP-only, no final ticket or candidate code. Cross-vendor rechecking should use existing verification only if it fits without new machinery; otherwise report the recommendation. These proposals are not a live authorization. Checkpoint C still governs publication.

## Project-owner identity follow-up (2026-11-15)

The owner requested replacing person-specific authority checks before public publication. Init records the project owner in host configuration (explicit option, Git name, OS login), and checkpoint-B approval matches that identity. Protected amendments must use the owner in the trusted base, with a regression test for simultaneous owner substitution. This request authorizes the protection-policy change; it does not authorize provider calls or publication. Land the owner and hash-bound amendment record before changing the anchored policy, so CI can check a prior trusted decision.

## Checkpoint B — live pilot, 2026-11-15

The project owner approved the first live pilot and chose the cheaper models of both vendors to save cost: `claude-sonnet-5-5` with Claude Code sign-in and `gpt-6.1-terra` with Sign in with ChatGPT, effort high, 8 worker runs per backend, 1 in parallel, 32 turns and 300 s per worker. No API key, no fallback, no retry until a positive result; every restart in a fresh directory.

Result: after six attempts that failed for technical reasons, C5 and O2 completed 8/8 supported on worker protocol v2. The record is [CHECKPOINT-B-PILOT](CHECKPOINT-B-PILOT.md). Scaling beyond 8 worker runs, other models or another problem need a new go.

## Checkpoint C — publication, 2026-11-15

The project owner approved publication. The repository was recreated with only `main` and set public on 2026-11-15 after green CI.

## Phase 4a authorization — 2026-11-15

The project owner authorized autonomous completion of the low-effort Phase 4a items, offline only: the seven `rloop-` skills (A6), their installer, `docs/GUIDE.md`, the `self-assess` entry point, and report wording that names the backend that actually ran. No provider calls, sign-in, new project authorization or live pilot.

Phase 4b, one licensed real problem from question to pilot, needs the owner's choice of problem and data, and a new go for its live pilot. Phase 5, the provider comparison on real work, follows 4b.

## Phase 4b authorization — 2026-11-15

The project owner chose autonomous mode as an end-to-end test of the framework: one licensed real problem, from question to live pilot. They set three conditions: keep token use low, prove that the framework works rather than aim for big science, and use one of the hackathon experiments as the benchmark. Selecting the problem within that mandate was part of the autonomous test.

- **Problem:** grain counting and sizing on 316L stainless steel micrographs. This is project #5 of the Claude Impact Lab 2026 event, from `VanishJr/micrograph-impact-lab` at commit `9175855`, Apache-2.0. Its pipeline and metric may be ported with attribution. Their published development (40 images) and holdout (165 images) numbers are the cited benchmark.
- **Data:** Zenodo record 22039777 (DOI 10.5281/zenodo.22039777), metadata license CC BY 4.0, from Warren et al., Computational Materials Science 233 (2024) 112739. Caveat: the deposit's README says a final license has not yet been selected inside the package. Therefore the images are never redistributed. Each user downloads the archive by DOI with hash checks, and the repository holds only code, derived statistics and provenance.
- **Pre-registration:** supported if the development `max_rel_error` is at most 0.10, the team's own target. Two controls must reproduce the team's numbers before any worker runs: defaults 12.885…, team final 0.12586….
- **Implementation:** offline. It includes one protected-evaluator change through the hash-bound authorization in `project.json`, with the owner as authority on the basis of this record.
- **Live pilot:**
  - `claude-sonnet-5-5` (Claude Code sign-in) and `gpt-6.1-terra` (Sign in with ChatGPT), effort high;
  - 4 worker runs per backend, 1 in parallel, 32 turns and 300 s per worker, 3600 s per project;
  - no API key, no fallback, no retry until a positive result, restarts only in fresh directories.
- **Final holdout:** the selected candidate per backend is evaluated on it once. A negative result is reported as such.

Result: both backends completed 4/4 on the first attempt, all `not supported`. The best development `max_rel_error` was 0.1259 (Terra, the published baseline) and 0.1414 (Sonnet). The holdout gave 0.1765 and 0.1818 against the cited 0.1739. The record is [PHASE-4B-PILOT](PHASE-4B-PILOT.md).

Scaling beyond this pilot and Phase 5 still need a new go.

## CNN feasibility on external compute — 2026-11-15

After the Phase 4b record, the owner identified the limiting factor: no run could reach the target because no model was trained. They directed a CNN feasibility test, chose Kaggle as the GPU host, set up its credentials and specified a vendor-agnostic compute layer for the repository (Kaggle, Google alternatives and others). The owner approved:

- **Compute layer:** `rloop compute` with the `local`, `kaggle`, `manual` and `command` adapters ([COMPUTE](COMPUTE.md)). Only code leaves the machine, never data. Kaggle kernels are always private, and the owner's Kaggle handle never enters tracked files.
- **One feasibility run:** a small U-Net on a private Kaggle kernel, after one smoke run ([experiments/grain-cnn](../experiments/grain-cnn/README.md)). The rule is pre-registered there and committed before the run. Val is scored once, locally, with the Phase 4b evaluator; the `test` split is never read.

Result: the first full run stopped in the data loader (mixed image formats; fixed in bd56566, no training happened). The second completed on a Tesla T4. Val `max_rel_error` 0.1639, scored once: worse than the team's 0.1259 and short of the 0.10 target. The record is [experiments/grain-cnn](../experiments/grain-cnn/README.md#attempt-log).

A worker loop around training, live use of other hosts, and any use of the holdout need a new go.

## Coached mode and competence profile — 2026-11-15

The owner specified a selectable competence-enhancing mode, modelled on their
PresentTogether repository, and approved its design.

The agent does the technical work and explains and suggests research methods;
the person decides. Autonomous remains the default. Coached mode adds four
moments for the person's view, named methods, reflection and a research brief.
The owner also specified a local competence profile that guides explanation
depth per area and is updated through learning progress, with changes confirmed
by the person. The shared scale, Markdown format and update rules match
PresentTogether; only the areas differ. Only the person's coaching agent
accesses `~/.competence-profiles/research-loops.md`; it stays outside projects,
reports, briefs, receipts and the ledger, and is never sent to workers or services.

Mode is a way of working, not a security barrier: the tool cannot verify who
wrote a prediction or rationale. This offline implementation grants no live
provider, compute, publication or holdout authorization.

## Record maintenance — 2026-11-15

Decision records use neutral paraphrase and name roles, not tools. On the
owner's instruction, earlier entries were reworded and the published history
from the Phase 4a record onward was rewritten; those commits have new hashes,
and hash references in these documents were updated. CI run numbers cited
elsewhere refer to the commits before the rewrite.

## Process identity race repair — 2026-11-15

The owner approved treating a process that vanishes during its identity read as
gone, including `ProcessLookupError`, while retaining integrity errors for other
read failures. The hash-bound authorization in `project.json` covers this process
supervision change and its manifest update. Numerical evaluation and the
planted-signal compatibility identity remain unchanged. The authorization must
be committed before the protected change; this grants no live-run permission.

## Local job interface — 2026-11-16

The owner approved read-only JSON status and report commands and a cancel
command so that a local module gateway can run `rloop` as a background job.
This offline interface grants no live-provider, pilot or holdout authorisation.
