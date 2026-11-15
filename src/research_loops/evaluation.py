"""Coordinator-only subprocess evaluator and independent arithmetic check."""

import json
import sys
from pathlib import Path

from research_loops.domain import IntegrityError, Verdict, canonical, digest
from research_loops.processes import supervised
from research_loops.protection import verify_anchor


def evaluator_hash(domain: str = "planted-signal") -> str:
    # Pin all modules that can affect the verdict, not a worker-provided manifest.
    manifest = verify_anchor()
    # Keep existing planted registrations stable across the domain extension.
    # This identity is owner-authorized alongside the full new package anchor;
    # verify_anchor still checks every protected file on every invocation.
    compatibility = manifest.get("domain_identities", {}).get(domain)
    if (domain == "planted-signal" and compatibility
            and compatibility["files"] == manifest["files"]):
        return compatibility["identity"]
    return digest(canonical(manifest).encode())


class SubprocessEvaluator:
    def evaluate(self, candidate: bytes, dataset: bytes, seconds: float, *, started=None, data_root: Path | None = None) -> Verdict:
        verify_anchor()
        request = json.loads(dataset)
        grain = request.get("domain") == "grain-316l"
        if grain:
            if data_root is None:
                raise IntegrityError("grain evaluator requires a separate host data root")
            request = {"domain": "grain-316l", "manifest": request, "data_root": str(data_root.resolve())}
        request["candidate"] = json.loads(candidate)
        output = supervised([sys.executable, "-I", "-m", "research_loops.evaluator_worker"],
            canonical(request).encode(), seconds, cwd=Path(sys.executable).parent, started=started)
        from research_loops.grain_evaluator import parse_verdict
        verdict = parse_verdict(output)
        if not grain and (len(verdict.predictions) != len(request["rows"]) or len(verdict.squared_errors) != len(request["rows"])):
            raise IntegrityError("incomplete per-example outputs")
        from research_loops.verification import check
        check(request, verdict)
        return verdict
