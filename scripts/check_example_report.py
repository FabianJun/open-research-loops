"""CI proof: rerun the fake example and compare with its committed report."""

import asyncio
import shutil
import tempfile
from pathlib import Path

from research_loops.coordinator import run
from research_loops.domain import IntegrityError


def check() -> None:
    example = Path(__file__).resolve().parents[1] / "examples" / "planted-signal"
    with tempfile.TemporaryDirectory(prefix="rloop-proof-") as folder:
        target = Path(folder)
        shutil.copyfile(example / "contract.json", target / "contract.json")
        asyncio.run(run(target))
        actual = (target / ".rloop" / "report.md").read_bytes()
        expected = (example / "expected-report.md").read_bytes()
        if actual != expected:
            raise IntegrityError("example report differs from committed fixture; review evidence before updating")
    print("committed example report matches fresh offline evidence")


if __name__ == "__main__":
    check()
