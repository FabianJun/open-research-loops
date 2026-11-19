"""Logged ideation and evidence-bound literature records; no retrieval fallback."""

from pydantic import Field

from research_loops.paths import atomic_write, long_path, plain_io_errors
from research_loops.domain import IntegrityError, Message, digest
from research_loops.grounding import quote
from research_loops.storage import Repository


class Idea(Message):
    id: str
    hypothesis: str
    rank: int = Field(ge=0, le=100)
    reason: str = Field(min_length=1)


def ideation(repo: Repository, proposals: list[Idea], keep: int) -> list[Idea]:
    if not 0 <= keep <= len(proposals) or len({p.id for p in proposals}) != len(proposals):
        raise IntegrityError("invalid idea selection")
    ranked = sorted(proposals, key=lambda idea: (-idea.rank, idea.id))
    with repo.db:
        for index, idea in enumerate(ranked):
            repo.event("idea", idea.id, {**idea.model_dump(), "disposition": "keep" if index < keep else "killed_on_paper", "criterion": "predeclared rank descending, ID tie-break"})
    return ranked[:keep]


@plain_io_errors()
def literature(repo: Repository, source_id: str, *, url: str, license: str,
               source: bytes | None = None, quotation: str | None = None, error: str | None = None) -> None:
    if not url or not license:
        raise IntegrityError("source URL and license (or explicit unknown) required")
    if error or source is None:
        with repo.db:
            repo.event("retrieval_failed", source_id, {"url": url, "license": license, "error": error or "no content"})
        raise IntegrityError("literature retrieval failed; model memory is not a source")
    quote(source, quotation or "")
    checksum = digest(source)
    path = repo.root / "objects" / checksum
    if not long_path(path).exists():
        atomic_write(path, source, exclusive=True)
    with repo.db:
        repo.event("literature", source_id, {"url": url, "license": license, "hash": checksum, "quote": quotation, "tag": "cited"})
