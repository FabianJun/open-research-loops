import asyncio
import json

import pytest

from research_loops.coordinator import run
from research_loops.reporting import render
from research_loops.storage import Repository


@pytest.mark.parametrize("live", [False, True])
def test_report_wording_uses_all_dispatch_metadata(example, live):
    payload = json.loads((example / "contract.json").read_bytes())
    payload.update(seeds=[7], variants_per_seed=2)
    (example / "contract.json").write_text(json.dumps(payload), encoding="utf-8")
    asyncio.run(run(example))
    asyncio.run(run(example, final=True))
    repo = Repository(example / ".rloop")
    try:
        original = render(repo)
        if live:
            # Saved metadata seam: mixed fake/model history, with no SDK or provider call.
            row = repo.runs()[0]
            metadata = json.loads(row["execution_metadata"])
            metadata["backend"] = "openai_agents"
            with repo.db:
                repo.db.execute("UPDATE runs SET execution_metadata=? WHERE id=?", (json.dumps(metadata), row["id"]))
        text = render(repo)
        tag = "measured" if live else "simulated"
        for statement in ("Attempted variants", "Selection", "Paired bootstrap development MSE improvement interval", "Final MSE"):
            assert f"[{tag}] {statement}:" in text
        assert "[cited] Synthetic dataset license: CC0-1.0." in text
        if live:
            assert text.startswith("# Planted signal — live model workers\n")
            assert "Real model workers on a known-answer sanity task: this tests the loop and evidence handling, not scientific discovery." in text
            assert "[simulated]" not in text
        else:
            assert text == original == (repo.root / "report.md").read_text(encoding="utf-8")
            assert text.startswith("# Planted signal — simulated\n")
            assert "Fake proposals demonstrate execution and evidence handling, not new scientific discovery." in text
    finally:
        repo.close()
