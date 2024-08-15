# test_retryable_aiohttp_client.py
import pytest
from aioresponses import aioresponses
from helix_fhir_client_sdk.utilities.retryable_aiohttp_client import (
    RetryableAioHttpClient,
)


@pytest.mark.asyncio
async def test_get_success() -> None:
    async with RetryableAioHttpClient(use_data_streaming=False) as client:
        with aioresponses() as m:
            m.get("http://test.com", status=200, payload={"key": "value"})
            response = await client.get(url="http://test.com", headers=None)
            assert response.ok
            assert response.status == 200
            assert await response.get_text_async() == '{"key": "value"}'


@pytest.mark.asyncio
async def test_retry_on_500() -> None:
    async with RetryableAioHttpClient(retries=2, use_data_streaming=False) as client:
        with aioresponses() as m:
            m.get("http://test.com", status=500)
            with pytest.raises(Exception):
                await client.get(url="http://test.com", headers=None)


@pytest.mark.asyncio
async def test_non_retryable_status_code() -> None:
    async with RetryableAioHttpClient(use_data_streaming=False) as client:
        with aioresponses() as m:
            m.get("http://test.com", status=400)
            response = await client.get(url="http://test.com", headers=None)
            assert not response.ok
            assert response.status == 400


@pytest.mark.asyncio
async def test_token_refresh_on_401() -> None:
    async def mock_refresh_token() -> str:
        return "new_token"

    async with RetryableAioHttpClient(
        simple_refresh_token_func=mock_refresh_token, use_data_streaming=False
    ) as client:
        with aioresponses() as m:
            m.get("http://test.com", status=401)
            m.get("http://test.com", status=200, payload={"key": "value"})
            response = await client.get(
                url="http://test.com", headers={"Authorization": "Bearer old_token"}
            )
            assert response.ok
            assert response.status == 200
            assert await response.get_text_async() == '{"key": "value"}'


@pytest.mark.asyncio
async def test_handle_429() -> None:
    async with RetryableAioHttpClient(use_data_streaming=False) as client:
        with aioresponses() as m:
            m.get("http://test.com", status=429, headers={"Retry-After": "1"})
            m.get("http://test.com", status=200, payload={"key": "value"})
            response = await client.get(url="http://test.com", headers=None)
            assert response.ok
            assert response.status == 200
            assert await response.get_text_async() == '{"key": "value"}'


@pytest.mark.asyncio
async def test_chunked_transfer_encoding() -> None:
    async with RetryableAioHttpClient(use_data_streaming=True) as client:
        with aioresponses() as m:
            m.get(
                "http://test.com",
                status=200,
                body="4\r\nWiki\r\n5\r\npedia\r\n0\r\n\r\n",
                headers={"Transfer-Encoding": "chunked"},
            )
            response = await client.get(url="http://test.com", headers=None)
            assert response.ok
            assert response.status == 200
            assert (
                await response.get_text_async()
                == "4\r\nWiki\r\n5\r\npedia\r\n0\r\n\r\n"
            )


async def test_no_exception_on_error() -> None:
    """Test merge_async call when throw_exception_on_error is false."""
    async with RetryableAioHttpClient(
        use_data_streaming=True, throw_exception_on_error=False
    ) as client:
        with aioresponses() as m:
            m.get(
                "http://test.com",
                status=400,
                body="Error",
                headers={"Transfer-Encoding": "chunked"},
            )
            response = await client.get(url="http://test.com", headers=None)
            assert not response.ok
            assert response.status == 400
            assert await response.get_text_async() == ""
