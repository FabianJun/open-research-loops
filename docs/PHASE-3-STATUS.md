# Phase 3 / 3b delivery status

Completed 2026-11-15 against the authorized private repository. Stops after Phase 3b, before Phase 4 and checkpoint-B provider calls. Owner decisions remain in [DECISIONS.md](DECISIONS.md).

## Built

- README leads with getting the first scientific experiment running. LESSONS records the preparation gap: instructions existed, but the toolkit had not run a real problem; the missing piece was runtime.
- `rloop init PROJECT --question "..."` creates the explicitly simulated planted-signal scaffold and completes a two-candidate fake pilot, including controls, registration, import, evaluation and report. The timing script verifies both completed outcomes. This does not supply a real problem's domain data or evaluator.
- All six existing service functions over MCP stdio. Direct/stdio parity covers results and traversal, evaluator/final-data and sealed-outbox refusals. Registered training samples are available through hash-checked, read-only `inputs/training.json`; development/final samples are never projected into the public directory.
- Optional `openai_agents` and `claude_agent` adapters behind AgentBackend. SDK versions remain locked: OpenAI Agents 0.24.0, OpenAI 3.51.0, Claude Agent SDK 0.2.182, MCP 2.3.0. Installed source APIs and test seams are recorded in PRIOR-ART. No SDK imports in the core.
- Shared offline pilot/contract tests use the OpenAI SDK's Model seam and Claude SDK's Transport seam, with real SDK orchestration and real MCP subprocesses. No provider runner is mocked out. The existing socket guard stays enabled with dummy keys present. Built-in tools are disabled; tests inspect Claude's SDK-built CLI flags and verify/reject the effective tool list. Tool-server environment audits contain names only and no credential variables.
- Provider/model/SDK/cost/usage/image metadata at dispatch and import, plus saved SDK traces. Fake cost is zero. SDK unknown cost stays null, appears as unknown in reports and retains its reservation. The only migration adds a consumed JSON column to runs; no new domain tables. Phase-2 report replay preserves its original bytes and remains a true no-op.
- Nonfake starts require matching owner/provider/model/positive USD-cap approval in project configuration, before SDK import or tool launch. The effective shared budget is the smaller of contract budget and approval cap. No approval was created.
- Sandbox none/container, OCI Containerfile with source allowlist, configurable Docker/Podman subprocess CLI, digest requirement, agreed mounts/network/non-root/read-only/tmpfs/capability/resource limits, stdio watchdog and cleanup. The worker image has no SDK, evaluator, holdout or database. All three backend profiles pass the container contract. Separate code-candidate evaluation containers mount holdout read-only; the host never imports candidate code.
- Four actual preflight probes fail closed: private/evaluator paths absent, persistent writes outside workspace refused, outbound network unavailable, and removal after a child-spawning timeout. Unknown daemon state cannot be mistaken for successful cleanup. DESIGN records the shared-kernel threat model and the bounded Windows NTFS ownership bridge.

The private remote's concurrent README commit `2c22ea2` was preserved through a fast-forward. No pushed history was rewritten. Implementation commits: `38a7e72` init, `463893c` MCP, `edcf0e5` SDKs, `241cbed` Sandbox, `68c395a` public training projection.

## Verified locally

Windows: uv 0.11.19, Python 3.12.13, Docker Desktop 29.8.1 with Linux engine. The final full run, including actual Linux worker containers:

```powershell
uv sync --locked --all-extras --python 3.12
docker build --file Containerfile --iidfile .sandbox-image .
$env:RLOOP_SANDBOX_IMAGE = (Get-Content .sandbox-image -Raw).Trim()
uv run --locked pytest -q
```

Result: **86 passed in 71.41s**, no skips. A separate base-only environment verified the documented minimal install without changing `.venv`:

```powershell
$env:UV_PROJECT_ENVIRONMENT = Join-Path (Get-Location) '.container-tests/base-venv'
uv sync --locked --python 3.12
uv run --locked pytest -q
```

Result: **57 passed, 4 skipped in 18.86s**. Skips explicitly request the optional MCP extra; the base core imports/runs without either vendor SDK.

Linux verification:

```powershell
powershell -NoProfile -File scripts/verify_linux.ps1
```

Final logged invocation used `cmd /c 'powershell -NoProfile -File scripts/verify_linux.ps1 > .container-tests/linux-public-inputs.log 2>&1'`; exit **0**. Result: **86 passed in 79.23s**, no skips, including actual sibling worker/evaluator containers for all adapters. Python 3.12.12, uv 0.9.30 in the pinned official uv base. The driver installs Docker CLI/Git only inside itself, mounts the repository read-only, and uses `/tmp/rloop-venv`, `/tmp/uv-cache` and a disposable Linux test volume. The Docker socket is mounted only in the trusted verification driver, never a worker. Driver and volume were removed. WSL and the Windows `.venv` were untouched by Linux verification.

Inside that driver, the exact final sequence after environment preparation was:

```sh
uv sync --locked --all-extras
uv run --locked pytest -q -o cache_dir=/tmp/pytest-cache
uv run --locked python scripts/measure_init.py
uv run --locked python scripts/check_protected.py --base HEAD
uv build --out-dir /tmp/rloop-dist
```

Additional Windows checks, all exit **0**:

```powershell
uv run --locked python scripts/check_example_report.py
uv run --locked python scripts/check_protected.py --base HEAD
uv run --locked python scripts/measure_init.py
uv build
git diff --check
```

The committed simulated report matches fresh evidence. Protected evaluator matches its trusted base; no numerical anchor was changed. Wheel and source distribution built on both OSes. Both commands below refused before any provider/tool launch with checkpoint-B-required messages and expected exit **2**:

```console
uv run --locked rloop run examples/planted-signal --backend openai_agents
uv run --locked rloop run examples/planted-signal --backend claude_agent
```

## Measured init-to-pilot time

`uv run --locked python scripts/measure_init.py` launches the actual isolated CLI in three fresh temporary projects and verifies two completed candidates, one negative and one supported. Clock starts at CLI launch and stops after the completed simulated pilot; it includes controls/evaluator startup and excludes installation/downloads. This is a conservative upper bound on the first experiment starting, not a measurement of real scientific domain setup.

| Environment | Seconds, three samples | Median |
|---|---|---|
| Windows | 1.059998, 1.030255, 1.053674 | **1.054 s** |
| Disposable Linux driver | 1.743464, 1.525358, 1.626694 | **1.627 s** |

These are observed warm-install timings, not a performance target or a claim about provider latency.

## GitHub CI

> [!NOTE]
> The run links below point to the private predecessor of this repository. The repository was recreated before it went public, so those runs are no longer reachable. Commit SHAs are unchanged; re-run the workflow on a SHA to reproduce a result.

The SDK step [43654130390](https://github.com/scaled-thinking/open-research-loops/actions/runs/43654130390) is green: Ubuntu 69 passed in 20.32s; Windows 69 passed in 35.16s. The Sandbox step [43656074784](https://github.com/scaled-thinking/open-research-loops/actions/runs/43656074784) is green: Ubuntu 83 passed in 62.02s; Windows 78 passed, 5 skipped in 46.13s. Each skip explicitly explains that GitHub Windows runners cannot run Linux containers.

Final implementation `68c395a`: [run 43656721319](https://github.com/scaled-thinking/open-research-loops/actions/runs/43656721319), both jobs green:

| Job | Command | Result |
|---|---|---|
| [offline (ubuntu-latest)](https://github.com/scaled-thinking/open-research-loops/actions/runs/43656721319/job/132636761573) | `uv run --locked pytest` | **86 passed in 69.30s**, actual container tests included. |
| [offline (windows-latest)](https://github.com/scaled-thinking/open-research-loops/actions/runs/43656721319/job/132636761731) | `uv run --locked pytest` | **80 passed, 6 skipped in 44.91s**; all skips visibly explain the Windows runner's lack of Linux containers. |

Both jobs also passed the locked install, fresh offline campaign, report check/export, committed-report regeneration and protected-evaluator trusted-base check. Earlier init/MCP pushes were also green; the legitimate README-only remote update was preserved.

Inspection commands: `gh run list --limit 5`, `gh run view RUN_ID --json jobs`, and `gh run view RUN_ID --log | Select-String -Pattern 'passed|skipped'`. On failures use `gh run view RUN_ID --log-failed`. Linux CI runs the actual container tests; a missing Linux CI runtime fails the fixture.

Initial Windows stdio exec behavior, SQLite timing cleanup, Docker Desktop file ownership and an older Linux Docker CLI's JSON formatting were corrected and verified. No failure remained after two targeted fixes.

## Not done / practical limits

- No provider call, spending, checkpoint-B authorization, public publication, release, tag, secret/settings change or force-push. No execution from refs, AGPL code copying, toolkit personal data or WSL changes.
- No Phase 4 skills/installer/GUIDE or Phase 5 provider comparison. Optional Codex/Claude Code CLI adapters remain deferred. No code-changing example or generic code-task scientific evaluator/CLI; code fixtures prove the Sandbox boundary only.
- SDK seams prove orchestration and configured isolation offline, not live provider availability, scientific ability or production SDK/CLI behavior against a provider. Podman uses tested common command flags but was not exercised against a Podman daemon. Hosted sandboxes and gVisor remain optional future adapters.
- Live SDK session recovery, general multi-contract planning and a real scientific problem remain later work. The fake oracle's performance is simulated engineering evidence.
- Live workers currently reserve the entire approved cap. Unknown-cost OpenAI runs keep that reservation and block another dispatch. Before a funded multi-worker pilot, agree and implement per-worker charge envelopes/reconciliation with headroom. Do not relabel an estimate as SDK-reported USD or zero. Existing zero-dollar contracts also require an explicit budget amendment. An SDK budget parameter is not an independently metered invoice guarantee.

## Open questions for checkpoint B, with recommendations

These are proposals for the project owner; none is an approval or project configuration.

| Decision | Recommendation |
|---|---|
| OpenAI provider/model? | Direct OpenAI API, `gpt-6-luna`, for a focused, inexpensive first transport/research pilot. Verify account access only after authorization. |
| Claude provider/model? | Direct Anthropic API, `claude-haiku-5-5`, for the latency-focused pilot. Any later Sonnet upgrade needs a separate model approval. |
| USD cap? | **USD 5 per backend, USD 10 combined maximum**, in separate fresh pilot projects. Treat this as a proposed spending ceiling, not a cost forecast; no automatic refill, fallback model or retries. |
| Charge envelope/headroom? | Start with one worker at a time and the current full-cap reservation. Resolve OpenAI's unreported USD from provider billing before another dispatch. Before a two-worker paid pilot, approve a checked per-worker rate/token/turn envelope with headroom and implement its reconciliation tests. Preserve unknown SDK costs as unknown. |
| Which example first, and how far? | `examples/planted-signal`, MCP-only declarative workers, a fresh registration per backend, public training samples, controls first, then a small paid pilot. No final holdout consumption or code changes. Start with one worker, then two after the charge-envelope decision. |
| First real scientific problem after the smoke test? | the project owner selects a bounded reproduction with licensed public inputs and a plain-code falsifier. Reuse the measured init workflow, while treating domain-data/evaluator setup as separate work; the synthetic oracle does not demonstrate research efficacy. |

Model IDs and descriptions checked 2026-11-15 against [OpenAI's model catalog](https://developers.openai.com/api/docs/models) and [Anthropic's model catalog](https://platform.claude.com/docs/en/models/overview). Choosing their inexpensive, focused models for this pilot is our recommendation, not a measured scientific ranking. Recheck access and prices at B.

## Next three steps

1. The project owner decides B: provider/model per backend, caps, charge envelope/headroom and the bounded pilot scope. Record the actual authorization and amend the corresponding contract budget; do not infer approval from this report.
2. Implement/test the agreed per-worker reservation and cost-reconciliation policy, then run only the explicitly authorized planted-signal pilot. Save provider traces, reported/unknown costs, negative results and checked verdicts; expand only after review.
3. In a separately authorized Phase 4, add the seven rloop-prefixed skills and short GUIDE, and take one licensed real problem from question to pilot while measuring its actual setup time. Publication remains checkpoint C.
