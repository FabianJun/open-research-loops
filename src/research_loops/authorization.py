"""Explicit owner authorization. Credentials never constitute permission to run."""

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from research_loops.domain import IntegrityError
from research_loops.owner import owner_name


class LimitReached(IntegrityError):
    """Stop the pilot without retries or credential/model fallback."""


class RunLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    max_worker_runs: int = Field(ge=1, le=256)
    max_parallel_workers: int = Field(ge=1, le=4)
    max_turns_per_worker: int = Field(ge=1, le=256)
    max_wall_seconds_per_worker: int = Field(ge=1, le=300)


class Authorization(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    approved_by: str
    provider: str
    model: str = Field(min_length=1)
    auth_mode: str
    run_limits: RunLimits
    effort: str = "high"
    usd_cap: str | int | float | None = None

    @property
    def cap_micro_usd(self) -> int | None:
        if self.usd_cap is None:
            return None
        try:
            value = Decimal(str(self.usd_cap))
            if not value.is_finite() or value < Decimal("0.000001"):
                raise ValueError()
            return int(value * 1_000_000)
        except (ValueError, InvalidOperation) as exc:
            raise IntegrityError("invalid checkpoint B USD cap") from exc


def authorize(project: Path | None, provider: str, model: str) -> Authorization:
    path = project / "project.json" if project else None
    if path is None or not path.is_file():
        raise IntegrityError("provider calls are not authorized: checkpoint B project configuration required")
    try:
        config = json.loads(path.read_bytes())
        owner = owner_name(config)
        value = config["checkpoint_b"]
        if "backends" in value:
            value = value["backends"][provider]
        approval = Authorization.model_validate(value)
        modes = {"openai": {"chatgpt", "api_key"}, "anthropic": {"claude_code", "api_key"}}
        if (approval.approved_by.strip() != owner or approval.provider != provider or approval.model != model
                or not model.strip() or approval.auth_mode not in modes.get(provider, set())
                or approval.effort not in {"low", "medium", "high", "xhigh", "max"}
                or (approval.usd_cap is not None and approval.auth_mode != "api_key")):
            raise ValueError()
        approval.cap_micro_usd
        return approval
    except (ValueError, KeyError, TypeError, ValidationError) as exc:
        raise IntegrityError("provider calls are not authorized: invalid checkpoint B provider, model, auth mode or run limits") from exc
