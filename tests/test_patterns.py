import asyncio

import pytest

from research_loops.domain import IntegrityError, WorkerContract
from research_loops.scheduler import fanout


def tasks():
    return [WorkerContract(run_id=f"variant-{i}", registration_hash="a" * 64, goal="recover signal",
        prediction=f"hypothesis {i}", seed=7, variant=i, input_hash="b" * 64) for i in range(4)]


@pytest.mark.parametrize("pattern", ["ideation", "independent_hypotheses", "best_of_n", "independent_recheck"])
def test_all_four_patterns_keep_each_result_and_isolate_scope(pattern):
    async def check():
        async def operation(item):
            await asyncio.sleep(0)
            return item.run_id, item.prediction
        result = await fanout(pattern, tasks(), operation, 4, pilot_ready=True, independent_method="exact_arithmetic")
        assert len(result) == 4
        assert len({row[0] for row in result}) == 4
    asyncio.run(check())


def test_model_change_alone_is_not_an_independent_recheck():
    async def operation(item):
        pytest.fail("invalid recheck must never dispatch")
    with pytest.raises(IntegrityError, match="different model"):
        asyncio.run(fanout("independent_recheck", tasks(), operation, 4, pilot_ready=True, independent_method="another_model"))


def test_pattern_guards_run_before_dispatch():
    async def operation(item):
        pytest.fail("invalid pattern must never dispatch")
    with pytest.raises(IntegrityError, match="pilot"):
        asyncio.run(fanout("best_of_n", tasks(), operation, 4))
    repeated = [item.model_copy(update={"prediction": "same hypothesis"}) for item in tasks()]
    with pytest.raises(IntegrityError, match="distinct"):
        asyncio.run(fanout("independent_hypotheses", repeated, operation, 4, pilot_ready=True))
