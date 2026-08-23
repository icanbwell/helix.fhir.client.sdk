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
