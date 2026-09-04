import asyncio
from typing import Any, cast

import pytest

from helix_fhir_client_sdk.utilities.async_parallel_processor.v1.async_parallel_processor import (
    AsyncParallelProcessor,
    ParallelFunctionContext,
)


async def double_it(
    *, context: ParallelFunctionContext, row: int, parameters: None, additional_parameters: dict[str, Any] | None
) -> int:
    return row * 2


@pytest.mark.parametrize("max_concurrent_tasks", [0, -1])
def test_init_rejects_non_positive_max_concurrent_tasks(max_concurrent_tasks: int) -> None:
    with pytest.raises(ValueError):
        AsyncParallelProcessor(name="test", max_concurrent_tasks=max_concurrent_tasks)


@pytest.mark.asyncio
async def test_yield_context_false_is_default_and_unchanged() -> None:
    processor = AsyncParallelProcessor(name="test", max_concurrent_tasks=1)
    results = [
        r async for r in processor.process_rows_in_parallel(rows=[1, 2, 3], process_row_fn=double_it, parameters=None)
    ]
    assert results == [2, 4, 6]


@pytest.mark.asyncio
async def test_yield_context_true_sequential() -> None:
    processor = AsyncParallelProcessor(name="test", max_concurrent_tasks=1)
    results: list[tuple[int, int, int]] = []
    async for item in processor.process_rows_in_parallel(
        rows=[1, 2, 3], process_row_fn=double_it, parameters=None, yield_context=True
    ):
        ctx, value = cast(tuple[ParallelFunctionContext, int], item)
        results.append((ctx.task_index, ctx.total_task_count, value))
    assert results == [(0, 3, 2), (1, 3, 4), (2, 3, 6)]


@pytest.mark.asyncio
async def test_yield_context_true_concurrent() -> None:
    processor = AsyncParallelProcessor(name="test", max_concurrent_tasks=2)
    results: list[tuple[int, int]] = []
    async for item in processor.process_rows_in_parallel(
        rows=[1, 2, 3], process_row_fn=double_it, parameters=None, yield_context=True
    ):
        ctx, value = cast(tuple[ParallelFunctionContext, int], item)
        results.append((ctx.task_index, value))
    # completion order isn't guaranteed under concurrency; task_index correctly
    # identifies which row each result belongs to regardless of arrival order
    assert sorted(results) == [(0, 2), (1, 4), (2, 6)]


@pytest.mark.asyncio
async def test_yield_context_false_at_concurrency_2_is_unchanged() -> None:
    # Regression guard for the concurrent branch too: default (yield_context=False)
    # must still yield bare TOutput values, not tuples, when max_concurrent_tasks > 1.
    processor = AsyncParallelProcessor(name="test", max_concurrent_tasks=2)
    results = [
        r async for r in processor.process_rows_in_parallel(rows=[1, 2, 3], process_row_fn=double_it, parameters=None)
    ]
    assert sorted(results) == [2, 4, 6]


async def succeed_or_fail(
    *, context: ParallelFunctionContext, row: str, parameters: None, additional_parameters: dict[str, Any] | None
) -> str:
    if row == "fail":
        raise ValueError("boom")
    return row


@pytest.mark.asyncio
async def test_concurrent_batch_yields_completed_siblings_before_raising() -> None:
    # asyncio.wait(..., return_when=FIRST_COMPLETED) can return more than one
    # simultaneously-completed task in a single `done` set, and iterating a
    # set does not preserve completion order. Neither task here performs a
    # real suspension (no I/O, semaphore has spare capacity), so both
    # complete on the very first event-loop pass and land in the same `done`
    # batch deterministically. A failing task must not cause an
    # already-succeeded sibling task's result in the same batch to be
    # silently discarded.
    processor = AsyncParallelProcessor(name="test", max_concurrent_tasks=2)

    results: list[str] = []
    with pytest.raises(ValueError, match="boom"):
        async for item in processor.process_rows_in_parallel(
            rows=["ok", "fail"], process_row_fn=succeed_or_fail, parameters=None
        ):
            results.append(item)

    assert results == ["ok"]


@pytest.mark.asyncio
async def test_process_rows_in_parallel_does_not_create_all_tasks_up_front() -> None:
    """Regression test: a prior implementation created one asyncio.Task per row
    immediately (via a set comprehension), before the loop even started, and
    relied on a semaphore only to gate entry into process_row_fn's body. That
    left every not-yet-scheduled row's Task object resident in memory at once
    regardless of max_concurrent_tasks - real, avoidable memory pressure for a
    large `rows` list. The fix is a bounded worker pool: at most
    max_concurrent_tasks Task objects exist at any moment, topped up one-for-one
    as each completes.
    """
    created_task_count = 0
    real_create_task = asyncio.create_task

    def counting_create_task(coro: Any, **kwargs: Any) -> "asyncio.Task[Any]":
        nonlocal created_task_count
        created_task_count += 1
        return real_create_task(coro, **kwargs)

    release = asyncio.Event()

    async def blocking_fn(
        *, context: ParallelFunctionContext, row: int, parameters: None, additional_parameters: dict[str, Any] | None
    ) -> int:
        await release.wait()
        return row

    max_concurrent_tasks = 2
    total_rows = 10
    processor = AsyncParallelProcessor(name="test", max_concurrent_tasks=max_concurrent_tasks)

    results: list[int] = []

    async def consume() -> None:
        async for r in processor.process_rows_in_parallel(
            rows=list(range(total_rows)), process_row_fn=blocking_fn, parameters=None
        ):
            results.append(r)

    consumer_task = real_create_task(consume())
    try:
        asyncio.create_task = counting_create_task
        # Give the event loop enough ticks to run process_rows_in_parallel up to
        # its first suspension point (every worker awaiting release.wait()).
        for _ in range(3):
            await asyncio.sleep(0)

        assert created_task_count == max_concurrent_tasks
    finally:
        asyncio.create_task = real_create_task
        release.set()
        await consumer_task

    assert sorted(results) == list(range(total_rows))
