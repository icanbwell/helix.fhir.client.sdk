import pytest
import asyncio
from typing import TypeVar
from helix_fhir_client_sdk.utilities.async_runner import AsyncRunner

T = TypeVar("T")


# Sample coroutine for testing
async def sample_coroutine() -> str:
    await asyncio.sleep(0.1)
    return "success"


# Test for AsyncRunner.run
def test_run() -> None:
    result: str = AsyncRunner.run(sample_coroutine())
    assert result == "success"


# Test for AsyncRunner.run with timeout
def test_run_with_timeout() -> None:
    result: str = AsyncRunner.run(sample_coroutine(), timeout=1.0)
    assert result == "success"


# Test for AsyncRunner.run_in_thread_pool_and_wait
def test_run_in_thread_pool_and_wait() -> None:
    result: str = AsyncRunner.run_in_thread_pool_and_wait(sample_coroutine())
    assert result == "success"


# Test for AsyncRunner.run when event loop is already running
@pytest.mark.asyncio
async def test_run_with_existing_event_loop() -> None:
    result: str = await asyncio.to_thread(
        AsyncRunner.run, sample_coroutine(), timeout=1.0
    )
    assert result == "success"
