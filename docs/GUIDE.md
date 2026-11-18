# Scientist and engineer guide

Want to learn research design as you work? Choose [coached mode](COACHED.md).

From a source checkout, install the `research-loops` distribution with uv.
`rloop` is the console command; `python -m research_loops.cli` invokes the same CLI.
Run the following from the checkout root;
`research-demo` should be a fresh directory. All commands here are offline.

```sh
uv sync --locked
uv run python -m research_loops.cli init research-demo
uv run python -c "from pathlib import Path; print(Path('research-demo/contract.json').read_text()); print(Path('research-demo/.rloop/report.md').read_text())"
uv run python -c "import json; from pathlib import Path; p=Path('research-demo/contract.json'); c=json.loads(p.read_text()); c['variants_per_seed']=2; p.write_text(json.dumps(c), encoding='utf-8')"
uv run python -m research_loops.cli plan research-demo --reason "Bound the follow-up to two variants per seed and arm"
uv run python -m research_loops.cli run research-demo --backend fake
uv run python -m research_loops.cli run research-demo --final
uv run python -m research_loops.cli report research-demo --check
uv run python -m research_loops.cli export research-demo
uv run python -m research_loops.cli self-assess research-demo --write
```

Init runs two fake workers after the controls. Read the contract and report
before choosing changes. The bounded follow-up above edits a supported field
in `contract.json` and records the amendment with `plan --reason`; it completes
the comparison with two variants per seed and arm, including negative results.
An amendment does not reset the shared attempt, time or cost allowances.

Each evaluation includes a separate exact-arithmetic implementation check.
`run --final` freezes the selection and consumes the one-use holdout ticket;
it seals the campaign. Self-assessment re-checks saved arithmetic without
dispatching experiments and separates machine facts from human questions.
Inspect `.rloop/report.md`, `events.jsonl` and `self-assessment.md` together.

Live pilots require the explicit owner gate described in
[CHECKPOINT-B-PREP](CHECKPOINT-B-PREP.md); the approved pilot and limits are in
[CHECKPOINT-B-PILOT](CHECKPOINT-B-PILOT.md). Neither credentials nor the commands
above authorize a live run. See [DESIGN](DESIGN.md) and [LESSONS](LESSONS.md).

Inspect the eight skills and preview personal-agent links:

```sh
uv run python -m research_loops.cli skills list
uv run python -m research_loops.cli skills show rloop-research-loop
uv run python -m research_loops.cli skills install --target both --dry-run
```

To install, remove `--dry-run`: links go to `~/.claude/skills` and
`~/.agents/skills` (junctions on Windows). Any conflicting target blocks the
whole install. `--target claude` or `--target agents` selects one location.
`skills show` provides text and its SHA-256 for explicit injection into your
own agent. Skills are not injected into pilot workers in this delivery.

## Planted-signal example

`rloop init` on a fresh directory runs the simulated planted-signal pilot. Median from command
start to finished pilot, three runs each and excluding installation: 1.152 s on Windows, 1.408 s on
Linux. `uv run python scripts/measure_init.py` reproduces it on your machine.

The report is rendered from the database. Each scored run links its evidence, and result lines carry
a provenance tag. In this excerpt, `(evidence)` stands for that link:

```text
| Run                 | Execution | Scientific outcome | Verification | Development MSE         |
|---------------------|-----------|--------------------|--------------|-------------------------|
| 46d657d8-agent-7-00 | completed | negative           | checked      | 28.421875 (evidence)    |
| 46d657d8-agent-7-01 | completed | supported          | checked      | 0 (evidence)            |

[simulated] Attempted variants: 2.
[measured] Control/final evaluation starts: 2.
[measured] External model cost: USD 0.000000 (offline fake only).
[cited] Synthetic dataset license: CC0-1.0.
```

The full example campaign runs 48 variants: an agent arm against a random baseline, eight per seed
across three registered seeds.

```console
uv run rloop run examples/planted-signal            # dispatch, import, evaluate; safe to repeat
uv run rloop status examples/planted-signal
uv run rloop report examples/planted-signal --check # regenerate from the DB and compare
uv run rloop run examples/planted-signal --final    # seal the campaign; allowed once
uv run pytest
```

Repeating `run` or `resume` never reruns a completed candidate.

## Machine interface

A local job runner can poll without taking the coordinator lock:

```console
rloop status PROJECT --json
rloop report PROJECT --json
rloop cancel PROJECT
```

Each command prints one JSON object. Status and JSON report are read-only:
no initialisation, migrations, report rewrites or project-file changes, including
SQLite WAL/shared-memory files. They read a stable committed snapshot in memory;
poll again if a concurrent update prevents a snapshot. Plain `status` uses the
same reader and retains its text format; plain `report` still generates files.

`rloop.status/1` fields:

| Field | Meaning |
|---|---|
| `schema` | `rloop.status/1` |
| `project_state` | `running` for an active coordinator job or running worker; otherwise `sealed` after final-ticket consumption, the latest job's terminal state (`completed`, `cancelled`, `technical_error`), or `completed`, `ready`, `unregistered` from saved runs/registration |
| `cancel_requested` | Whether the active coordinator job has a matching pending request |
| `runs` | All saved worker attempts, ordered by ID |
| `runs[].id` | Immutable worker attempt ID |
| `runs[].execution_status` | Saved execution state: `running`, `completed`, `technical_error`, `timed_out`, `interrupted`, `cancelled` or `limit_reached` |
| `runs[].scientific_outcome` | Saved `supported` or `negative`; `null` when unevaluated |
| `runs[].started_at` | Stored dispatch timestamp, ISO 8601 UTC |
| `runs[].finished_at` | Terminal ledger-event timestamp, ISO 8601 UTC, or `null` if absent |
| `runs[].prediction_registered` | Whether a numerical project prediction was registered for this attempt's registration; excludes worker prediction prose |
| `runs[].report_paths` | Existing project report paths, relative to PROJECT: `markdown` and/or `html`; `null` if absent. A saved report may predate an active run. |

`rloop.report/1` returns the same `project_state` and `cancel_requested`, plus
the shared Markdown run-table summary. Each `runs[]` entry has `id`,
`execution_status`, `scientific_outcome`, `started_at`, `finished_at` and
`prediction_registered` as above; `verification_status` is the saved check
state, `backend` is the dispatch backend, and `development_metrics` holds only
stored development `mse` or grain `max_rel_error`, `median_count_rel_error` and
`median_size_rel_error` (empty before evaluation; undefined values are `null`).
`attempted_variants` counts attempts; `control_final_evaluation_starts` counts
control/final starts; `spent_micro_usd` and `reserved_micro_usd` are ledger totals;
`selected_run_id` is the saved selection or `null`. No raw evaluations, holdout
data, worker prose, owner settings or absolute paths are exposed.

Errors use the command's schema and `error: {code, message}`, with exit code 2:
`no_database` before initialisation, `not_ready` for a report without any finished
worker attempt, or `unreadable_project` when the snapshot cannot be read.
Successful commands exit 0. JSON report never rewrites Markdown or HTML.

`cancel` atomically writes `.rloop/cancel.json` without taking the project lock.
Its `rloop.cancel/1` confirmation contains `job_id` (the active coordinator
invocation's ledger ID, distinct from worker attempt IDs, or `null`) and
`cancel_requested`. Repeated requests for the same job leave the file unchanged.
An idle request has `cancel_requested: false`; it does not cancel the next job.
Requests remain bound to their job ID, so a stale file is ignored by later jobs.
An abrupt coordinator exit can leave a job marked active until the next run or
resume; polling reports saved state, not an operating-system liveness probe.

Cancellation is checked before dispatch, while waiting, and before evaluation.
Workers are cancelled through existing process-tree cleanup; an evaluator that
already started is awaited before the ledger closes. Dispatched unfinished
attempts and the job finish as `cancelled`, and reports and the event hash chain
are exported. Undispatched assignments are not fabricated as attempts.
`resume` reconciles saved work without dispatching or re-evaluating cancelled
attempts; a later `run` may dispatch assignments that never started.

## Grain 316L benchmark

Install the optional `grain` extra (`uv sync --locked --all-extras` includes it).
With a previously obtained `Grain.zip` in the checkout root, the following is
offline and leaves the holdout unspent. Start with a fresh `grain-demo` directory.

```powershell
uv run python -c "import shutil; shutil.copytree('examples/grain-316l', 'grain-demo')"
uv run rloop init grain-demo --owner "Your Name"
uv run rloop data fetch grain-demo --archive Grain.zip
uv run rloop plan grain-demo
uv run rloop run grain-demo --backend fake
uv run rloop report grain-demo --check
uv run rloop self-assess grain-demo --write
```

This is a real benchmark with a published baseline; fake proposals remain
simulated. Both development controls must reproduce within 1e-9 before workers
run. Worker protocol v3 exposes training statistics and a six-call
`try_on_training(params)` tool on a fixed subset, with one candidate per run.
Planted-signal retains protocol v2 and its six tools. Read
[provenance](../examples/grain-316l/PROVENANCE.md) for the unresolved package
license and the no-redistribution rule. The live pilot runs
under the [Phase 4b record](DECISIONS.md#phase-4b-authorization--2026-11-15),
using fresh projects and existing explicit provider gates. Only a later
`run --final` consumes the selected candidate's final ticket.

Documentation licensed CC BY 4.0.
