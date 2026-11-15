# Scientist and engineer guide

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

Inspect the seven skills and preview personal-agent links:

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
