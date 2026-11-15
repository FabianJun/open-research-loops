"""Grain controls and the deterministic offline worker; no provider calls."""

import asyncio
import json

from research_loops.domain import IntegrityError, canonical
from research_loops.grain_evaluator import CONTROL_VALUES, TEAM_FINAL
from research_loops.paths import atomic_write


def control_expectations():
    # Only tests monkeypatch this function in process. No CLI/contract/env override.
    return CONTROL_VALUES


def controls(repo, contract, key):
    from research_loops.coordinator import data_root, private
    from research_loops.evaluation import SubprocessEvaluator
    values, evidence = [], []
    expected = control_expectations()
    for name, config, target in zip(("defaults", "team_final"), ({}, TEAM_FINAL), expected, strict=True):
        repo.reserve_control()
        result = SubprocessEvaluator().evaluate(canonical(config).encode(), private(repo, key, "development"),
            contract.limits.evaluator_seconds, data_root=data_root(repo, contract, "development"))
        values.append(result.max_rel_error)
        evidence.append(dict(name=name, params=config, expected=target, measured=result.max_rel_error,
            reproduced=abs(result.max_rel_error - target) <= 1e-9, verdict=result.model_dump(mode="json")))
    with repo.db:
        repo.event("grain_controls", key, {"controls": evidence})
    if not all(item["reproduced"] for item in evidence):
        raise IntegrityError(f"grain controls failed: defaults measured {values[0]!r}, expected {expected[0]!r}; team final measured {values[1]!r}, expected {expected[1]!r}; absolute tolerance 1e-9; workers blocked")
    repo.pilot(dict(positive_control=True, negative_control=True, nonconstant=True, baseline=True))


def prepare_training_tool(repo, contract, key, run_root):
    from research_loops.coordinator import data_root, private
    manifest = json.loads(private(repo, key, "training"))
    manifest["images"] = manifest["images"][:32]
    # Host-private capability file; never included in worker instructions/context.
    # It carries one split only. The service never receives project configuration,
    # the DB path, or development/final roots or manifests.
    value = {"manifest": manifest, "data_root": str(data_root(repo, contract, "training").resolve())}
    atomic_write(run_root / "training-tool.json", canonical(value).encode(), exclusive=True)


class GrainFakeBackend:
    async def run(self, contract, workspace, limits):
        from research_loops.tools import ToolService
        tools = ToolService(contract, workspace.root)
        tools.read_contract()
        tools.read_artifact("inputs/training.json")
        tools.register_variant(contract.prediction)
        params = TEAM_FINAL if contract.arm == "agent" else {}
        await asyncio.to_thread(tools.try_on_training, params)
        return tools.submit_result(params)
