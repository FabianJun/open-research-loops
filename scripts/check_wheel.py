"""Run via an isolated wheel install, never through the editable source package."""

import asyncio
import json
import tempfile
from pathlib import Path

import research_loops
from research_loops.coordinator import run
from research_loops.storage import Repository


assert "site-packages" in Path(research_loops.__file__).parts, "expected an isolated installed wheel"
with tempfile.TemporaryDirectory(prefix="rloop-wheel-") as folder:
    root = Path(folder)
    (root / "contract.json").write_text(json.dumps({"goal": "wheel proof", "falsifier": "mismatch",
        "prediction": "oracle works", "seeds": [7], "variants_per_seed": 2}), encoding="utf-8")
    asyncio.run(run(root))
    asyncio.run(run(root, final=True))
    repo = Repository(root / ".rloop")
    assert len(repo.runs()) == 4
    assert all(row["execution_status"] == "completed" for row in repo.runs())
    assert json.loads(repo.db.execute("SELECT final_ticket FROM project").fetchone()[0])["state"] == "completed"
    repo.close()
print("installed wheel: offline run, migrations, evaluator, report/export and final passed")
