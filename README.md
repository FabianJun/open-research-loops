# open-research-loops

Bounded experiments with saved evidence, protected evaluation and reproducible reports.
Python 3.12+, Windows and Linux. Code: Apache-2.0; documentation: CC BY 4.0.

```console
uv sync --locked
uv run rloop run examples/planted-signal
uv run rloop status examples/planted-signal
uv run rloop run examples/planted-signal --final
uv run pytest
```

Outputs live in `examples/planted-signal/.rloop/`. Repeating `run` reconciles saved work without rerunning completed candidates. Final evaluation seals the campaign and can be requested once. Reports label the example as simulated; fake proposals demonstrate the machinery, not scientific discovery.

The distribution is `research-loops` (`uv pip install research-loops`); its console command is `rloop`. The unrelated PyPI `rloop` Rust asyncio package is never a dependency.

Phase 2 delivers the offline core. MCP transport, OpenAI/Claude SDK adapters, OCI sandbox execution, portable skills and the scientist/engineer guide are later work. Worktrees and virtual environments are not sandboxes. Code execution is refused in this delivery; the fake backend uses restricted tool functions directly and makes no network calls.

See [internal design](docs/DESIGN.md), [decisions](docs/DECISIONS.md) and [requirements](docs/REQUIREMENTS.md). The core is independently implemented; toolkit and third-party ideas are credited in [prior art](docs/PRIOR-ART.md).
