import asyncio
from asyncio import Task
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import (
    Any,
    Protocol,
    runtime_checkable,
)


@dataclass(slots=True)
class ParallelFunctionContext:
    """
    This class contains the parameters for a parallel function
    """

    """ name of the processor """
    name: str

    """ log level """
    log_level: str | None

    """ index of the task """
    task_index: int

    """ total number of tasks """
    total_task_count: int


@runtime_checkable
class ParallelFunction[TInput, TOutput, TParameters](Protocol):
    async def __call__(
        self,
        *,
        context: ParallelFunctionContext,
        row: TInput,
        parameters: TParameters | None,
        additional_parameters: dict[str, Any] | None,
    ) -> TOutput:
        """
        Handle a batch of data

        :param row: row to process
        :param parameters: parameters to pass to the process_row_fn
        :param additional_parameters: additional parameters
        :return: result of processing
        """
        ...


class AsyncParallelProcessor:
    def __init__(
        self,
        *,
        name: str,
        max_concurrent_tasks: int | None = None,
    ) -> None:
        """
        This class is used to process rows in parallel

        :param name: name of the processor
        :param max_concurrent_tasks: maximum number of concurrent tasks. If None, there is no limit.
                                    If 1 then the tasks are processed sequentially else they are processed in parallel
        """
        self.name: str = name
        self.max_concurrent_tasks: int | None = max_concurrent_tasks
        self.semaphore: asyncio.Semaphore | None = (
            asyncio.Semaphore(max_concurrent_tasks) if max_concurrent_tasks else None
        )

    async def process_rows_in_parallel[
        TInput,
        TOutput,
        TParameters: dict[str, Any] | object,
    ](
        self,
        *,
        rows: list[TInput],
        process_row_fn: ParallelFunction[TInput, TOutput, TParameters],
        parameters: TParameters | None,
        log_level: str | None = None,
        yield_context: bool = False,
        **kwargs: Any,
    ) -> AsyncGenerator[TOutput, None]:
        """
        Given a list of rows, it calls the process_row_fn for each row in parallel and yields the results

        :param rows: list of rows to process
        :param process_row_fn: function to process each row
        :param parameters: parameters to pass to the process_row_fn
        :param log_level: log level
        :param yield_context: if False (the default, preserving existing behavior for every
                               pre-existing caller), yields bare TOutput values exactly as
                               before. If True, yields (ParallelFunctionContext, TOutput)
                               tuples instead, so callers can recover which row (via
                               context.task_index) each result belongs to.
        :param kwargs: additional parameters
        :return: results of processing
        """

        if self.max_concurrent_tasks == 1:
            for i, row in enumerate(rows):
                context = ParallelFunctionContext(
                    name=self.name,
                    log_level=log_level,
                    task_index=i,
                    total_task_count=len(rows),
                )
                result = await process_row_fn(
                    context=context,
                    row=row,
                    parameters=parameters,
                    additional_parameters=kwargs,
                )
                yield (context, result) if yield_context else result  # type: ignore[misc]
            return

        # noinspection PyShadowingNames
        async def process_with_semaphore_async(
            *, name: str, row1: TInput, task_index: int, total_task_count: int
        ) -> tuple[ParallelFunctionContext, TOutput]:
            context = ParallelFunctionContext(
                name=name,
                log_level=log_level,
                task_index=task_index,
                total_task_count=total_task_count,
            )
            if self.semaphore is None:
                result = await process_row_fn(
                    context=context, row=row1, parameters=parameters, additional_parameters=kwargs
                )
            else:
                async with self.semaphore:
                    result = await process_row_fn(
                        context=context, row=row1, parameters=parameters, additional_parameters=kwargs
                    )
            return context, result

        total_task_count: int = len(rows)

        # Create all tasks at once with their indices
        pending: set[Task[tuple[ParallelFunctionContext, TOutput]]] = {
            asyncio.create_task(
                process_with_semaphore_async(
                    name=self.name,
                    row1=row,
                    task_index=i,
                    total_task_count=total_task_count,
                ),
                name=f"task_{i}",  # Optionally set task name for easier debugging
            )
            for i, row in enumerate(rows)
        }

        try:
            while pending:
                done: set[Task[tuple[ParallelFunctionContext, TOutput]]]
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)

                # Process completed tasks
                for task in done:
                    try:
                        context, result = await task
                        yield (context, result) if yield_context else result  # type: ignore[misc]
                    except Exception:
                        # Handle or re-raise error
                        # logger.error(f"Error processing row: {e}")
                        raise

        finally:
            # Cancel any pending tasks if something goes wrong
            for task in pending:
                task.cancel()
