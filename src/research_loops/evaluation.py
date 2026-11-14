"""Coordinator-only subprocess evaluator and independent arithmetic check."""

import json
import os
import subprocess
import sys
from pathlib import Path

from research_loops.domain import IntegrityError, Verdict, canonical, digest


def evaluator_hash() -> str:
    # Pin all modules that can affect the verdict, not a worker-provided manifest.
    folder = Path(__file__).parent
    return digest(b"".join((folder / name).read_bytes() for name in ("evaluator_worker.py", "domain.py", "evaluation.py")))


class SubprocessEvaluator:
    def evaluate(self, candidate: bytes, dataset: bytes, seconds: float) -> Verdict:
        request = json.loads(dataset)
        request["candidate"] = json.loads(candidate)
        env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "LANG"}}
        try:
            result = subprocess.run([sys.executable, "-I", "-m", "research_loops.evaluator_worker"],
                input=canonical(request).encode(), capture_output=True, timeout=seconds, env=env,
                cwd=Path(sys.executable).parent)
        except subprocess.TimeoutExpired as exc:
            raise IntegrityError("evaluator timed out") from exc
        if result.returncode or not result.stdout or len(result.stdout) > 1_000_000:
            raise IntegrityError("evaluator failed or returned empty/oversized output")
        verdict = Verdict.model_validate_json(result.stdout)
        if len(verdict.predictions) != len(request["rows"]) or len(verdict.squared_errors) != len(request["rows"]):
            raise IntegrityError("incomplete per-example outputs")
        # Independent metric path over sealed outputs; does not rerun the final split.
        from fractions import Fraction
        errors = [(Fraction(str(p)) - row["y"]) ** 2 for p, row in zip(verdict.predictions, request["rows"], strict=True)]
        expected = float(sum(errors) / len(errors))
        if abs(expected - verdict.mse) > 1e-12:
            raise IntegrityError("independent arithmetic check failed")
        return verdict
