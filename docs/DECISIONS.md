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
