"""Explicit provenance and report binding validation."""

from typing import Literal

from research_loops.domain import IntegrityError, Message


class Statement(Message):
    text: str
    tag: Literal["measured", "simulated", "cited", "assumed", "interpretation", "hypothesis"]


def quote(source: bytes, text: str) -> None:
    if not text or text not in source.decode("utf-8"):
        raise IntegrityError("quote is not a verbatim source substring")


def number(actual: float, claimed: str, fmt: str = ".12g") -> None:
    if claimed != format(actual, fmt):
        raise IntegrityError("reported number differs from evidence binding")


def public_context(payload: dict) -> None:
    allowed = {"run_id", "registration_hash", "goal", "prediction", "seed", "variant", "arm", "input_hash"}
    if set(payload) != allowed:
        raise IntegrityError("worker context is not the exact public projection")
