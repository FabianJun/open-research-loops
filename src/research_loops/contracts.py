"""Domain selection without changing the original planted-signal messages."""

import json
from typing import Literal

from pydantic import Field, field_validator

from research_loops.domain import Contract, Limits, Message, WorkerContract

DOI = "10.5281/zenodo.22039777"
ARCHIVE_SHA256 = "30ca8e80392519bb790d6093b5deb86df4d4aedf8cbe9beedbf329106d54d9d0"


class GrainContract(Message):
    schema_version: Literal[1] = 1
    name: Literal["grain-316l"] = "grain-316l"
    goal: str = "Count and size grains on 316L micrographs with development max_rel_error <= 0.10."
    falsifier: str = "Development max_rel_error exceeds 0.10."
    prediction: str = "A bounded parameter search may improve on the cited team development baseline."
    license: Literal["CC-BY-4.0"] = "CC-BY-4.0"
    dataset_doi: Literal["10.5281/zenodo.22039777"] = DOI
    archive_sha256: Literal["30ca8e80392519bb790d6093b5deb86df4d4aedf8cbe9beedbf329106d54d9d0"] = ARCHIVE_SHA256
    threshold_max_rel_error: Literal[0.10] = .10
    seeds: tuple[int, ...] = (7,)
    variants_per_seed: int = Field(default=2, ge=2, le=32)
    keep_margin: float = Field(default=1e-9, ge=0)
    limits: Limits = Limits(max_attempts=16, concurrency=1, worker_seconds=300,
        evaluator_seconds=300, project_seconds=3600)

    @field_validator("seeds")
    @classmethod
    def unique_seeds(cls, value):
        return Contract.unique_seeds(value)


class GrainWorkerContract(WorkerContract):
    domain: Literal["grain-316l"] = "grain-316l"
    worker_protocol: Literal[3] = 3


def parse_contract(value):
    if isinstance(value, (str, bytes)):
        value = json.loads(value)
    return (GrainContract if value.get("name") == "grain-316l" else Contract).model_validate(value)


def parse_worker(value):
    if isinstance(value, (str, bytes)):
        value = json.loads(value)
    return (GrainWorkerContract if value.get("domain") == "grain-316l" else WorkerContract).model_validate(value)


def is_grain(contract):
    return getattr(contract, "name", getattr(contract, "domain", None)) == "grain-316l"
