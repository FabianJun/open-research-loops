"""Coordinator-only subprocess evaluator and independent arithmetic check."""

import json
import sys
from pathlib import Path

from research_loops.domain import IntegrityError, Verdict, canonical, digest
from research_loops.processes import supervised
from research_loops.protection import verify_anchor


def evaluator_hash() -> str:
    # Pin all modules that can affect the verdict, not a worker-provided manifest.
    return digest(canonical(verify_anchor()).encode())


class SubprocessEvaluator:
    def evaluate(self, candidate: bytes, dataset: bytes, seconds: float, *, started=None) -> Verdict:
        verify_anchor()
        request = json.loads(dataset)
        request["candidate"] = json.loads(candidate)
        output = supervised([sys.executable, "-I", "-m", "research_loops.evaluator_worker"],
            canonical(request).encode(), seconds, cwd=Path(sys.executable).parent, started=started)
        verdict = Verdict.model_validate_json(output)
        if len(verdict.predictions) != len(request["rows"]) or len(verdict.squared_errors) != len(request["rows"]):
            raise IntegrityError("incomplete per-example outputs")
        from research_loops.verification import check
        check(request, verdict)
        return verdict
