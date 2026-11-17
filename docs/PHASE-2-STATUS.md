# Phase 1-2 delivery status

Completed locally 2026-11-15. Scope: [checkpoint A](DECISIONS.md); stopped before Phase 3.

## Built

- Locked Python 3.12 package, optional SDK dependency extras (not installed by default), Apache-2.0 code and CC BY 4.0 docs, NOTICE, AGENTS/CLAUDE pointer, Windows/Linux CI workflow.
- Offline `init`, `plan`, `run`, `status`, `resume`, `report`, `export`; fake-only CLI and import authorization. No SDK or MCP imports in the core.
- The vertical slice was committed before the integrity increments: registration → fake direct tools → sealed outbox → validated content-addressed import → protected evaluator subprocess → verdict → database-derived report/export.
- Subsequent tested increments: immutable registrations/predictions/evidence, exact duplicate-import no-op, per-example outputs and source fingerprints, controls/pilot, shared limits, four-worker/four-pattern scheduler, seeded selection and descriptive intervals, independent stack/rational verification, claims/challenges, grounding, logged ideation/retrieval failures, license checks, protected evaluator anchor policy, one-use final evaluation and crash reconciliation.
- Five incremental migrations; seven domain tables plus migration bookkeeping. No speculative task, agent, source, reservation or dependency tables.

The working example has 48 completed candidate runs: 45 negative and 3 supported, all checked. The oracle is deliberately supplied by fake. The comparison is **simulated engineering evidence**, not evidence of agent research ability. Two evaluator controls also count against the project allowance; a final attempt would be the 51st start. Final tests use disposable projects; the working example remains unsealed.

## Windows verification

Windows 11, CPython 3.12.13, uv 0.11.19. Commands run from the repository root:

| Exact command | Result |
|---|---|
| `uv sync --locked --python 3.12` | Base environment installed; vendor SDK extras absent. |
| `uv run --locked pytest -q` | **57 passed in 12.62s**; no skipped tests. |
| `uv run --locked rloop run examples/planted-signal` | Exit 0; 48 completed runs, report and export saved. |
| `uv run --locked rloop report examples/planted-signal --check` | Exit 0; saved report equals database regeneration. |
| `uv run --locked rloop export examples/planted-signal` | Exit 0; existing prefix preserved. |
| `uv run --locked rloop resume examples/planted-signal` | Exit 0; completed work not rerun. |
| `uv run --locked python scripts/check_example_report.py` | Exit 0; fresh offline evidence matches committed fixture. |
| `uv run --locked python scripts/check_protected.py --base HEAD` | Exit 0; working anchor matches local HEAD and protected files. Initial anchor adoption still needs owner review; this is not proof of prior human authorization. |
| `uv build` | Exit 0; sdist and wheel built. |
| `uv run --no-project --isolated --python 3.12 --with .\dist\research_loops-0.1.0-py3-none-any.whl python -I scripts/check_wheel.py` | Exit 0; actual site-packages wheel completes run, migrations, evaluator, report/export and final. |
| `git diff --check` | Exit 0. |

Tests cover wrong/empty/malformed/nonfinite results, evaluator timeout with a real grandchild, a real killed coordinator, dead/live/reused process identities, crash boundaries and durable final receipts, final data unopened before the ticket, budget/attempt/time exhaustion, failed-pilot blocking, paths with spaces/non-ASCII, traversal, Windows junction/Linux symlink refusal, grounding and append-only export. External sockets are denied in the test process while dummy API keys are present; Windows asyncio's internal loopback wakeup sockets are allowed. Evaluator subprocesses receive a sanitized environment without API keys.

## Linux verification

Disposable official uv image, Python 3.12.12, **uv 0.9.30**. The attempted version-specific `0.11.19-python3.12-bookworm-slim` tag did not exist. The available Python-3.12 image was pulled and pinned to the digest below. The checkout is mounted read-only; both virtual environment and cache are outside it. No WSL installation or configuration was changed.

Exact final command (PowerShell):

```powershell
docker run --rm --mount 'type=bind,source=<checkout>,target=/workspace,readonly' --workdir /workspace --env UV_PROJECT_ENVIRONMENT=/tmp/rloop-venv --env UV_CACHE_DIR=/tmp/uv-cache ghcr.io/astral-sh/uv@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58 /bin/sh -c 'uv --version && python --version && uv sync --locked && uv run --locked pytest -q -o cache_dir=/tmp/pytest-cache && uv run --locked python scripts/check_example_report.py && uv build --out-dir /tmp/rloop-dist'
```

Final command exited 0: **57 passed in 20.94s**, no skips or warnings; committed report matched fresh evidence; sdist and wheel built under `/tmp/rloop-dist`.

An earlier extra Git-anchor check failed because the slim image has no Git. Installing Git only inside a second disposable container resolved it; that check and the Linux build then exited 0. Exact corrective command:

```powershell
docker run --rm --mount 'type=bind,source=<checkout>,target=/workspace,readonly' --workdir /workspace --env UV_PROJECT_ENVIRONMENT=/tmp/rloop-venv --env UV_CACHE_DIR=/tmp/uv-cache ghcr.io/astral-sh/uv@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58 /bin/sh -c 'apt-get update -qq && apt-get install -y -qq --no-install-recommends git && git config --global --add safe.directory /workspace && uv sync --locked && uv run --locked python scripts/check_protected.py --base HEAD && uv build --out-dir /tmp/rloop-dist'
```

## Limits and work not done

- No GitHub CI run was initiated or verified as part of the Phase 1-2 work. A final inspection found `origin` configured as `https://github.com/scaled-thinking/open-research-loops.git`, absent at the start; earlier local commit IDs had also changed. The Phase 1-2 work did not configure a remote, create a GitHub repository or push. That external Git state was preserved; it does not authorize publication. Locally exercised commands are the verification evidence.
- No Phase 3 MCP transport or OpenAI/Claude SDK adapters, no paid/provider request. Generic report metadata is vendor-neutral; this release's import policy permits only zero-cost offline fake reports.
- No Phase 3b Sandbox adapters, OCI launcher, Containerfile or isolation probes. The Docker use above is a verification environment, not an implementation of worker sandboxing. Candidate code execution is refused. A worktree, venv or evaluator subprocess is not a sandbox.
- The four fan-out policies are tested primitives. Generic multi-problem/dependency planning, mixed live backends and SDK session recovery remain later work; this CLI executes planted-signal only. Ideation/literature are logged APIs with no network retriever or interactive planner.
- No source skills, installer, GUIDE or full SELF-ASSESSMENT yet; these remain Phase 4-5. Future skill names use the approved `rloop-` prefixes without wrappers.
- Evaluator upgrades in an existing campaign fail closed. The initial protected anchor needs owner review, and later upgrades need a prior human authorization in the trusted base; there is no runtime authorization-import command yet.
- Unknown process identity or a launch intent without a receipt blocks replay. A started final ticket without a durable result remains consumed. Failed variants stay counted; there is no automatic repair/retry loop. JSONL is not yet a database restore command.
- `.rloop/` evidence stays local and ignored. Earlier construction-only demo outputs were archived under ignored `refs/`; nothing from `refs/` was executed. The committed report is a simulated regression fixture; evidence links resolve in the generated runtime report. Publication files remain checkpoint C.

## Next three steps

1. Phase 3: add MCP stdio transport and test parity with the direct service functions.
2. Phase 3: add both required SDK adapters and shared offline contract/isolation tests, with built-in tools disabled. Real calls still require checkpoint B's provider/model/USD cap.
3. Phase 3b: implement Sandbox none/container using configurable Docker/Podman CLI, OCI digest/mount/resource policy and preflight probes. Linux/local tests; explicit reason for Windows GitHub container-test skips.

No work on these steps was started in Phases 1-2.
