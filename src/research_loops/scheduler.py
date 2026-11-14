"""Small bounded pool; state mutations remain on the coordinator event loop."""

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import TypeVar

from research_loops.domain import IntegrityError

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
