# open-research-loops

Move a real scientific problem forward by getting the first experiment running quickly, then iterating with saved evidence and protected evaluation. **Time to the first running experiment is the headline goal.**

This repository carries lessons from *Claude Impact Lab x Foresight Institute — AI Research Loops for Open Science Problems* . It turns the method into a small executable runtime.
Python 3.12+, Windows and Linux. Code: Apache-2.0; documentation: CC BY 4.0.

```console
uv sync --locked
uv run rloop init my-pilot --question "Can we recover a planted nonlinear signal?"
uv run rloop run examples/planted-signal
uv run rloop status examples/planted-signal
uv run rloop run examples/planted-signal --final
uv run pytest
```

Outputs live in `examples/planted-signal/.rloop/`. Repeating `run` reconciles saved work without rerunning completed candidates. Final evaluation seals the campaign and can be requested once. Reports label the example as simulated; fake proposals demonstrate the machinery, not scientific discovery.
`init` creates the simulated planted-signal scaffold and completes a fake pilot. A real scientific question still needs its domain data, contract and evaluator. Run `uv run python scripts/measure_init.py` to measure command-to-completed-pilot time locally; installation/download time is excluded.

The distribution is `research-loops` (`uv pip install research-loops`); its console command is `rloop`. The unrelated PyPI `rloop` Rust asyncio package is never a dependency.

Phase 2 delivers the offline core. MCP transport, OpenAI/Claude SDK adapters, OCI sandbox execution, portable skills and the scientist/engineer guide are later work. Worktrees and virtual environments are not sandboxes. Code execution is refused in this delivery; the fake backend uses restricted tool functions directly and makes no network calls.

See [internal design](docs/DESIGN.md), [decisions](docs/DECISIONS.md) and [requirements](docs/REQUIREMENTS.md). The core is independently implemented; toolkit and third-party ideas are credited in [prior art](docs/PRIOR-ART.md).
