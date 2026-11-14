import asyncio
import json
import shutil
import sqlite3
from pathlib import Path

from research_loops.coordinator import run
from research_loops.reporting import export, report
from research_loops.storage import Repository


def test_offline_vertical_slice(tmp_path):
    example = tmp_path / "space ü" / "example"
    example.mkdir(parents=True)
    shutil.copyfile(Path(__file__).parents[1] / "examples/planted-signal/contract.json", example / "contract.json")
    asyncio.run(run(example))
    repo = Repository(example / ".rloop")
    try:
        rows = repo.runs()
        assert len(rows) == 48
        assert {r["scientific_outcome"] for r in rows} == {"negative", "supported"}
        assert all(r["execution_status"] == "completed" and r["verification_status"] == "checked" for r in rows)
        assert len(json.loads(rows[1]["verdict"])["predictions"]) == 64
        saved = (repo.root / "events.jsonl").read_bytes()
        report(repo, check=True)
        export(repo)
        assert saved == (repo.root / "events.jsonl").read_bytes()
    finally:
        repo.close()
    asyncio.run(run(example))
