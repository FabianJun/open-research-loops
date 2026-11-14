"""Measure a warm-install CLI start through a completed fake pilot; no target."""

import json
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path


def measure(repetitions: int = 3) -> dict:
    samples = []
    for _ in range(repetitions):
        with tempfile.TemporaryDirectory(prefix="rloop-init-") as folder:
            root = Path(folder) / "pilot"
            start = time.perf_counter()
            subprocess.run([sys.executable, "-I", "-m", "research_loops.cli", "init", str(root),
                "--question", "Can we recover a planted signal?"], check=True, capture_output=True)
            elapsed = time.perf_counter() - start
            with closing(sqlite3.connect(root / ".rloop" / "state.sqlite")) as db:
                rows = db.execute("SELECT execution_status,scientific_outcome FROM runs").fetchall()
                assert len(rows) == 2 and all(row[0] == "completed" for row in rows)
                assert {row[1] for row in rows} == {"negative", "supported"}
            samples.append(elapsed)
    return {"scope": "warm install; CLI start to two completed simulated pilot candidates; excludes installation",
        "backend": "fake", "seconds": samples, "median_seconds": statistics.median(samples)}


if __name__ == "__main__":
    print(json.dumps(measure(), sort_keys=True))
