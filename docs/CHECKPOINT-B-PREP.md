# Checkpoint-B preparation

Prepared offline on 2026-11-15. **No live run is authorized.** No real sign-in, OAuth/API request, provider call, credential-file inspection or project authorization was performed. The decisions and still-proposed choices are recorded in [DECISIONS.md](DECISIONS.md). Phase 4 and publication remain outside this delivery.

## Built

- Both SDK adapters remain optional and vendor-neutral. Subscription auth is the default: each user's Claude Code login, and OpenAI's public-client Sign in with ChatGPT token-sharing flow. API-key mode requires explicit project selection; keys never authorize execution or trigger fallback.
- Claude runs through the SDK Transport protocol with a filtered child environment, no inherited overriding credential/routing variables, no settings discovery, no hooks, no built-in tools, and the existing exact six-tool check. Retry/watchdog/background execution are disabled. A stub CLI process exercises the actual SDK handshake, verifies environment names and emits a rejected rate-limit event. No Claude credential file is opened by the framework. `--bare` is excluded because it disables subscription login.
- OpenAI sign-in includes dynamic registration, stable host UUID, app name hint, loopback callback, state/nonce/PKCE, issued-client binding and cryptographic ID-token verification. Separate account registrations and selection use opaque labels. The protected user store is outside repo/project; Unix owner permissions or Windows protected owner-only DACLs precede writes. Atomic refresh handles rotating tokens and serializes across processes. Missing direct-usage scope refuses inference.
- The OpenAI client receives the access token explicitly as its async `api_key` provider, against the public Responses endpoint. Model discovery exposes only listed slugs; the worker pins that account for every turn. The actual Agents SDK streams through a stub HTTP/SSE endpoint and real MCP tools; requests disable storage, include history/encrypted reasoning, namespace the six tools and omit preview-unsupported fields. A completed terminal event is mandatory. Pre-stream admission limits also stop without retry. Codex extension/app-server built-ins are not used.
- The gate now requires owner, provider, exact model, auth mode, effort and four run limits. Durable worker/parallel counters include failed attempts. SDK turn and coordinator wall-time limits stop execution. Rate/usage limits become `limit_reached`, stop dispatch and cancel siblings, with no retry/fallback. A saved limit result blocks another dispatch in that pilot after restart. Existing contract ceilings still apply. No new table or migration.
- Every nonfake dispatch records auth/model/SDK/effort/limits and explicitly estimated cost. Unknown usage/cost remains unknown; completed SDK usage is saved. Subscription USD estimates do not enter the charge ledger. Optional API-key caps retain the conservative reservation behavior; they are not a provider invoice guarantee.
- `rloop pilot PROJECT --backend NAME --workers 8` runs controls and bounded registered proposals without final selection or final-data consumption. Backend-specific IDs prevent saved results from suppressing another backend's work. Public README stays short; internal DESIGN, REQUIREMENTS, PRIOR-ART and repository instructions reflect this delivery.

Locked APIs checked in installed source: OpenAI Agents 0.24.0, OpenAI 3.51.0, Claude Agent SDK 0.2.182 and MCP 2.3.0. PyJWT[crypto] 2.15.1 is now an explicit OpenAI-extra dependency; cryptography 50.0.2 remains locked. [PRIOR-ART](PRIOR-ART.md) records the source files and seams; [DESIGN](DESIGN.md) links official auth/model documents and records preview restrictions.

## Verification

Windows: uv 0.11.19, Python 3.12.13, Docker Desktop 29.8.1 Linux engine. Commands:

```powershell
uv sync --locked --all-extras --python 3.12
uv run --locked pytest -q
```

Final result: **123 passed in 92.35s**, no skips, including actual Linux worker/evaluator containers. Focused checks also passed: `uv run --locked pytest -q tests/test_authorization.py` — **9 passed in 6.67s**; `uv run --locked pytest -q tests/test_openai_auth.py tests/test_chatgpt_responses.py` — **28 passed in 14.70s**; the final full run includes the encrypted-reasoning request option and pinned-account/pre-stream-limit cases. Socket guard and dummy API keys remain active; OAuth/API tests inject endpoints and never contact a provider.

Linux verification:

```powershell
cmd /c "powershell -NoProfile -File scripts/verify_linux.ps1 > .container-tests/linux-checkpoint-b-verified.log 2>&1"
```

Final exit **0**: **123 passed in 90.32s**, no skips. The disposable driver uses the pinned official uv image (Python 3.12.12, uv 0.9.30), read-only repository mount, `UV_PROJECT_ENVIRONMENT=/tmp/rloop-venv`, external cache/test volume, and actual sibling OCI containers. Driver/volume cleanup was verified. WSL and Windows `.venv` were not changed by Linux verification. Its exact checks after disposable package setup:

```sh
uv sync --locked --all-extras
uv run --locked pytest -q -o cache_dir=/tmp/pytest-cache
uv run --locked python scripts/measure_init.py
uv run --locked python scripts/check_protected.py --base HEAD
uv build --out-dir /tmp/rloop-dist
```

Additional Windows checks, all exit **0**:

```powershell
uv run --locked rloop auth preflight --backend claude_agent
uv run --locked rloop pilot --help
uv run --locked python scripts/measure_init.py
uv run --locked python scripts/check_example_report.py
uv run --locked python scripts/check_protected.py --base HEAD
uv build
git diff --check
```

Preflight reports configured auth mode only, with no network or credential reads. The simulated report still matches fresh offline evidence. Numerical anchors are unchanged. Wheel and source distribution build on both OSes. Both commands below refused before SDK/tool launch with the expected checkpoint-B-required message and exit **1**:

```console
uv run --locked rloop pilot examples/planted-signal --backend openai_agents --workers 8
uv run --locked rloop pilot examples/planted-signal --backend claude_agent --workers 8
```

Warm-install init-to-completed-fake-pilot timings (CLI startup, controls and two candidates; excludes installation): Windows **1.178735 / 1.151790 / 1.080726 s**, median **1.152 s**; final Linux run **1.513499 / 1.365201 / 1.407606 s**, median **1.408 s**. These are observations, not targets or live-provider timings.

Implementation commit `3862d35`; concurrent README clarification `6dbf2f4` was preserved in merge `acebb26`, with no pushed-history rewrite. [GitHub run 43659595886](https://github.com/scaled-thinking/open-research-loops/actions/runs/43659595886) on `acebb26` is green on both jobs, verified with `gh run view 43659595886 --json status,conclusion,jobs` and `gh run view 43659595886 --log`:

| CI job | `uv run --locked pytest` result | Other checks |
|---|---|---|
| offline (ubuntu-latest) | **119 passed in 77.73s** | Full fake campaign, report check/export, committed report regeneration and protected-base check passed. |
| offline (windows-latest) | **113 passed, 6 skipped in 56.44s** | Same checks passed. All six skips explicitly explain that GitHub Windows runners cannot run Linux containers; Linux CI executes them. |

Final implementation fix `4468691`: [run 43660437230](https://github.com/scaled-thinking/open-research-loops/actions/runs/43660437230), inspected with `gh run view 43660437230 --json status,conclusion,jobs` and `gh run view 43660437230 --log`, is also green:

| CI job | `uv run --locked pytest` result | Other checks |
|---|---|---|
| offline (ubuntu-latest) | **123 passed in 68.66s** | Full fake campaign, report/export, committed report regeneration and protected-base check passed. |
| offline (windows-latest) | **117 passed, 6 skipped in 61.33s** | Same checks passed; the six Linux-container skips retain their visible reason. |

## The project owner's steps at go

These are instructions for the project owner later. **The JSON below is an example, not an authorization.** Final model/effort/limits remain the owner's decision. Start with separate fresh pilot directories so their deadlines and accounting are independent.

1. Install the locked extras with `uv sync --locked --all-extras --python 3.12`. For Claude, run the offline framework check:

   ```console
   uv run --locked rloop auth preflight --backend claude_agent
   ```

   Open `claude`, use `/status` to confirm their own subscription login and `/model` to confirm the exact chosen model is available. If needed, use `/login` with their own Claude account, then `/exit`. Do not open, copy or paste credential files. An ambient key shown in `/status` must not be mistaken for subscription login; the worker independently removes overriding variables.

2. Sign in to OpenAI with your own account, then inspect the current account catalog:

   ```console
   uv run --locked rloop auth login-openai
   uv run --locked rloop auth models
   ```

   Complete **Continue with ChatGPT** in the system browser. `rloop auth accounts` shows the active opaque registration; `rloop auth accounts --select LABEL` switches saved registrations. Prefer `gpt-6-astra` only if listed. If unavailable, explicitly decide whether to choose listed `gpt-6.1-sol`; there is no automatic fallback. These commands do not request inference, but do perform the explicitly invoked sign-in/discovery requests. No such command was run here.

3. Run `uv run --locked rloop init pilots/claude --owner "Your Name"` and `uv run --locked rloop init pilots/openai --owner "Your Name"`. These run only the fake pilot and record the owner and its source in host-only `project.json`. Omit `--owner` to use Git's `user.name`, otherwise the OS login. Repeated init retains an existing owner unless `--owner` explicitly replaces it. Before registering provider workers, add this `limits` object to each contract:

   ```json
   {
     "max_attempts": 51,
     "concurrency": 1,
     "worker_seconds": 300,
     "evaluator_seconds": 10,
     "project_seconds": 3600,
     "budget_micro_usd": 0
   }
   ```

   The default example's 10-second worker/300-second project ceilings would otherwise remain in force. The proposed 300-second per-worker ceiling accommodates high-effort model/tool turns; it is not a latency forecast. Controls count against contract attempts, separate from checkpoint B's worker count. Init already registered the fake pilot's original contract; after changing these limits, register the amendment explicitly with `uv run --locked rloop plan pilots/claude --reason "Set owner-approved provider pilot limits"` and the equivalent command for `pilots/openai`. The provider pilot will check controls against that amended registration.

4. **Only after explicit go**, add `checkpoint_b` to each existing `project.json`, preserving its `owner` record and other settings. Replace `YOUR RECORDED OWNER` below with the recorded `owner.name`; approval matching strips whitespace and is case-sensitive. Proposed Claude content:

   ```json
   {
     "owner": {"name": "YOUR RECORDED OWNER", "source": "argument"},
     "sandbox": {"name": "none"},
     "checkpoint_b": {
       "approved_by": "YOUR RECORDED OWNER",
       "provider": "anthropic",
       "model": "claude-fable-5-2",
       "auth_mode": "claude_code",
       "effort": "high",
       "run_limits": {
         "max_worker_runs": 8,
         "max_parallel_workers": 1,
         "max_turns_per_worker": 32,
         "max_wall_seconds_per_worker": 300
       }
     }
   }
   ```

   Proposed `pilots/openai/project.json`, only if Astra is listed and the project owner approves:

   ```json
   {
     "owner": {"name": "YOUR RECORDED OWNER", "source": "argument"},
     "sandbox": {"name": "none"},
     "checkpoint_b": {
       "approved_by": "YOUR RECORDED OWNER",
       "provider": "openai",
       "model": "gpt-6-astra",
       "auth_mode": "chatgpt",
       "effort": "high",
       "run_limits": {
         "max_worker_runs": 8,
         "max_parallel_workers": 1,
         "max_turns_per_worker": 32,
         "max_wall_seconds_per_worker": 300
       }
     }
   }
   ```

   No `usd_cap` belongs in either subscription approval. To choose API-key mode later, explicitly set `auth_mode: "api_key"`; an optional positive `usd_cap` also requires a compatible contract budget and the API-key charge-policy decision below.

5. Register and run the bounded pilots, one backend at a time:

   ```console
   uv run --locked rloop plan pilots/claude
   uv run --locked rloop pilot pilots/claude --backend claude_agent --workers 8
   uv run --locked rloop report pilots/claude --check
   uv run --locked rloop plan pilots/openai
   uv run --locked rloop pilot pilots/openai --backend openai_agents --workers 8
   uv run --locked rloop report pilots/openai --check
   ```

   Inspect saved outcomes, tokens/estimated or unknown cost and SDK traces. A negative scientific verdict is valid evidence; do not retry until positive. On `limit_reached`, stop and review with the project owner. Do not rerun to reset limits, choose another billing path, consume final data or expand to 48 workers automatically.

## Not done

No real sign-in, account model discovery or inference; no account entitlement or live preview compatibility claim. No authorization file, paid/API-key pilot, 48-worker pilot, code-changing example, hosted sandbox, Phase-4 GUIDE/skills or public publication. No credential files were inspected. API-key charge-envelope/reconciliation remains conservative and unresolved for multi-worker funded campaigns. Cross-vendor critique was not added: the existing verifier requires independent computation, and model critique would need a new evidence workflow.

## Open questions and recommendations

| Owner decision | Recommendation |
|---|---|
| Final model per subscription? | Claude `claude-fable-5-2`, high effort; OpenAI listed `gpt-6-astra`, high effort. If unavailable, owner explicitly chooses listed `gpt-6.1-sol` or stops. Verify IDs/entitlement again at go; no cheaper automatic fallback. |
| Approve the run-limit proposal? | Eight workers per backend, one parallel worker, 32 turns and 300 seconds per worker, in separate 3600-second pilot contracts. Review actual traces/outcomes before any 48-worker approval. |
| Subscription credits or overage? | The project owner reviews the app's settings in [ChatGPT Usage](https://chatgpt.com/settings/usage) and their Claude subscription before go. Do not infer free/unlimited usage from subscription auth or an SDK USD estimate. Stop on limits; no API-key fallback. |
| USD cap in API-key mode? | Defer API-key pilots. If chosen, approve a cap, matching contract budget and checked per-worker charge envelope/reconciliation first. Current full-cap reservation plus unknown-cost retention is intentionally conservative; estimates are not invoices. |
| Cross-vendor recheck? | Compare the two pilots' claims as critique after their evidence is saved. Keep exact-arithmetic/computational verification authoritative. Approve a separate review workflow only if that critique proves useful. |
| First example and next real problem? | Planted-signal first, controls and public training only, no final ticket or code changes. Then the project owner chooses one licensed scientific reproduction with a concrete falsifier; measure that domain setup separately. |

## Next three steps

1. The project owner confirms model/auth/effort/limits and account usage settings, completes their own logins and creates the project approval only at go.
2. Run only the approved eight-worker planted-signal pilots; review negative/positive outcomes, limits and token/estimated-cost evidence before expanding.
3. With separate authorization, build the short Phase-4 GUIDE and seven rloop skills around one real scientific problem. Publication remains checkpoint C.
