"""Coordinator-only subprocess evaluator and independent arithmetic check."""

import json
import sys
from pathlib import Path

from research_loops.domain import IntegrityError, Verdict, canonical, digest
from research_loops.processes import supervised


def evaluator_hash() -> str:
    # Pin all modules that can affect the verdict, not a worker-provided manifest.
    folder = Path(__file__).parent
    return digest(b"".join((folder / name).read_bytes() for name in ("evaluator_worker.py", "domain.py", "evaluation.py")))


class SubprocessEvaluator:
    def evaluate(self, candidate: bytes, dataset: bytes, seconds: float, *, started=None) -> Verdict:
        request = json.loads(dataset)
        request["candidate"] = json.loads(candidate)
        output = supervised([sys.executable, "-I", "-m", "research_loops.evaluator_worker"],
            canonical(request).encode(), seconds, cwd=Path(sys.executable).parent, started=started)
        verdict = Verdict.model_validate_json(output)
        if len(verdict.predictions) != len(request["rows"]) or len(verdict.squared_errors) != len(request["rows"]):
            raise IntegrityError("incomplete per-example outputs")
        # Independent metric path over sealed outputs; does not rerun the final split.
        from fractions import Fraction
        errors = [(Fraction(str(p)) - row["y"]) ** 2 for p, row in zip(verdict.predictions, request["rows"], strict=True)]
        expected = float(sum(errors) / len(errors))
        if abs(expected - verdict.mse) > 1e-12:
            raise IntegrityError("independent arithmetic check failed")
        return verdict
