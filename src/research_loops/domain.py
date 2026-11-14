"""Canonical contracts and worker/evaluator messages; no provider dependencies."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IntegrityError(ValueError):
    """Saved evidence or an attempted operation violates the contract."""


def canonical(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_hash(value: Any) -> str:
    return digest(canonical(value).encode())


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Limits(Message):
    max_attempts: int = Field(default=51, ge=1, le=256)
    concurrency: int = Field(default=4, ge=1, le=4)
    worker_seconds: float = Field(default=10, gt=0, le=300)
    evaluator_seconds: float = Field(default=10, gt=0, le=300)
    project_seconds: float = Field(default=300, gt=0, le=3600)
    budget_micro_usd: int = Field(default=0, ge=0)


class Contract(Message):
    schema_version: Literal[1] = 1
    name: Literal["planted-signal"] = "planted-signal"
    goal: str
    falsifier: str
    prediction: str
    threshold_mse: float = Field(default=1e-12, ge=0)
    minimum_improvement: float = Field(default=0.99, ge=0, le=1)
    keep_margin: float = Field(default=1e-9, ge=0)
    seeds: tuple[int, ...] = (7, 13, 29)
    variants_per_seed: int = Field(default=8, ge=2, le=32)
    bootstrap_seed: int = 42
    bootstrap_resamples: int = Field(default=1000, ge=10, le=10000)
    license: Literal["CC0-1.0"] = "CC0-1.0"
    limits: Limits = Limits()

    @field_validator("seeds")
    @classmethod
    def unique_seeds(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if not value or len(set(value)) != len(value):
            raise ValueError("seeds must be nonempty and unique")
        return value


class Artifact(Message):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=1, le=1_000_000)


class WorkerReport(Message):
    report_id: str
    run_id: str
    contract_hash: str
    candidate: Artifact
    prompt_hash: str
    transcript: Artifact
    seed: int
    backend: Literal["fake"] = "fake"
    provider: Literal["offline"] = "offline"
    model: Literal["deterministic-v1"] = "deterministic-v1"
    cost_micro_usd: Literal[0] = 0


class Verdict(Message):
    mse: float = Field(ge=0)
    baseline_mse: float = Field(gt=0)
    improvement: float
    supported: bool
    predictions: tuple[float, ...]
    squared_errors: tuple[float, ...]


class WorkerContract(Message):
    run_id: str
    registration_hash: str
    goal: str
    prediction: str
    seed: int
    variant: int
    arm: Literal["agent", "random"] = "agent"
    input_hash: str


class Workspace(Message):
    root: Path


def validate_candidate(tree: Any, depth: int = 0, count: list[int] | None = None) -> None:
    count = [0] if count is None else count
    count[0] += 1
    if depth > 4 or count[0] > 31 or not isinstance(tree, dict):
        raise IntegrityError("candidate exceeds bounded expression schema")
    if set(tree) == {"feature"} and type(tree["feature"]) is int and 0 <= tree["feature"] < 4:
        return
    if set(tree) == {"constant"} and type(tree["constant"]) is int and -10 <= tree["constant"] <= 10:
        return
    if set(tree) != {"op", "left", "right"} or tree["op"] not in ("add", "sub", "mul"):
        raise IntegrityError("invalid candidate node")
    validate_candidate(tree["left"], depth + 1, count)
    validate_candidate(tree["right"], depth + 1, count)
