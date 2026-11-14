"""Small bounded pool; state mutations remain on the coordinator event loop."""

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import TypeVar
from typing import Literal

from research_loops.domain import IntegrityError, WorkerContract

T = TypeVar("T")
R = TypeVar("R")


async def bounded(items: Iterable[T], operation: Callable[[T], Awaitable[R]], concurrency: int) -> list[R]:
    if not 1 <= concurrency <= 4:
        raise IntegrityError("concurrency must be between one and four")
    semaphore = asyncio.Semaphore(concurrency)
    async def one(item):
        async with semaphore:
            return await operation(item)
    # TaskGroup cancels siblings and awaits their cleanup on any failure.
    tasks = []
    async with asyncio.TaskGroup() as group:
        for item in items:
            tasks.append(group.create_task(one(item)))
    return [task.result() for task in tasks]


async def fanout(pattern: Literal["ideation", "independent_hypotheses", "best_of_n", "independent_recheck"],
                 assignments: Iterable[WorkerContract], operation: Callable[[WorkerContract], Awaitable[R]],
                 concurrency: int, *, pilot_ready: bool = False, independent_method: str | None = None) -> list[R]:
    """Validate a pattern before any dispatch; operation owns persistence/evidence gates."""
    items = list(assignments)
    if not items or len({item.run_id for item in items}) != len(items):
        raise IntegrityError("fan-out requires nonempty unique assignments")
    if pattern not in {"ideation", "independent_hypotheses", "best_of_n", "independent_recheck"}:
        raise IntegrityError("unknown fan-out pattern")
    if pattern != "ideation" and not pilot_ready:
        raise IntegrityError("pilot required before compute fan-out")
    if pattern == "independent_hypotheses" and len({item.prediction for item in items}) != len(items):
        raise IntegrityError("independent hypotheses need distinct pre-dispatch predictions")
    if pattern == "best_of_n" and len({item.registration_hash for item in items}) != 1:
        raise IntegrityError("best-of-N must compare one registered contract")
    if pattern == "independent_recheck" and independent_method not in {"separate_implementation", "fresh_data", "exact_arithmetic"}:
        raise IntegrityError("a different model alone is not independent verification")
    return await bounded(items, operation, concurrency)
