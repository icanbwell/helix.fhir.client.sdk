# test_retryable_aiohttp_client.py
import asyncio

import pytest
from aiohttp import ClientSession
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


@pytest.mark.asyncio
async def test_put_method_success() -> None:
    """Test successful PUT request."""
    async with RetryableAioHttpClient(use_data_streaming=False) as client:
        with aioresponses() as m:
            m.put("http://test.com", status=200, payload={"key": "value"})
            response = await client.put(
                url="http://test.com",
                headers={"Content-Type": "application/json"},
                json={"data": "test"},
            )
            assert response.ok
            assert response.status == 200
            assert await response.get_text_async() == '{"key": "value"}'


@pytest.mark.asyncio
async def test_patch_method_success() -> None:
    """Test successful PATCH request."""
    async with RetryableAioHttpClient(use_data_streaming=False) as client:
        with aioresponses() as m:
            m.patch("http://test.com", status=200, payload={"key": "updated"})
            response = await client.patch(
                url="http://test.com",
                headers={"Content-Type": "application/json"},
                json={"data": "update"},
            )
            assert response.ok
            assert response.status == 200
            assert await response.get_text_async() == '{"key": "updated"}'


@pytest.mark.asyncio
async def test_delete_method_success() -> None:
    """Test successful DELETE request."""
    async with RetryableAioHttpClient(use_data_streaming=False) as client:
        with aioresponses() as m:
            m.delete("http://test.com", status=204)
            response = await client.delete(url="http://test.com", headers={})
            assert response.ok
            assert response.status == 204


@pytest.mark.asyncio
async def test_token_refresh_max_retries() -> None:
    """Test token refresh fails after maximum retries."""
    retry_count = 0

    async def mock_refresh_token() -> str:
        nonlocal retry_count
        retry_count += 1
        return f"token_{retry_count}"

    async with RetryableAioHttpClient(
        simple_refresh_token_func=mock_refresh_token,
        retries=2,
        use_data_streaming=False,
    ) as client:
        with aioresponses() as m:
            # Simulate multiple 401 responses
            m.get("http://test.com", status=401)
            m.get("http://test.com", status=401)
            m.get("http://test.com", status=401)

            with pytest.raises(Exception) as excinfo:
                await client.get(
                    url="http://test.com", headers={"Authorization": "Bearer old_token"}
                )

            assert "Unauthorized" in str(excinfo.value)
            assert retry_count == 3


@pytest.mark.asyncio
async def test_custom_session_creation() -> None:
    """Test custom session creation function."""
    session_created = False

    def custom_session_creator() -> ClientSession:
        nonlocal session_created
        session_created = True
        return ClientSession()

    async with RetryableAioHttpClient(
        fn_get_session=custom_session_creator, use_data_streaming=False
    ) as client:
        with aioresponses() as m:
            m.get("http://test.com", status=200, payload={"key": "value"})
            response = await client.get(url="http://test.com")

            assert session_created
            assert response.ok
            assert response.status == 200


@pytest.mark.asyncio
async def test_exclude_status_codes_from_retry() -> None:
    """Test excluding specific status codes from retry."""
    async with RetryableAioHttpClient(
        retries=3, exclude_status_codes_from_retry=[502], use_data_streaming=False
    ) as client:
        with aioresponses() as m:
            m.get("http://test.com", status=502)
            response = await client.get(url="http://test.com")

            assert not response.ok
            assert response.status == 502


@pytest.mark.asyncio
async def test_compression_and_chunked_transfer() -> None:
    """Test request with compression and chunked transfer."""
    async with RetryableAioHttpClient(
        use_data_streaming=True, compress=True, send_data_as_chunked=True
    ) as client:
        with aioresponses() as m:
            m.post(
                "http://test.com",
                status=200,
                body="Compressed and chunked data",
                headers={"Transfer-Encoding": "chunked", "Content-Encoding": "gzip"},
            )
            response = await client.post(
                url="http://test.com",
                headers={"Content-Type": "application/json"},
                json={"large": "payload"},
            )

            assert response.ok
            assert response.status == 200


@pytest.mark.asyncio
async def test_timeout_handling() -> None:
    """Test timeout handling with custom timeout."""
    async with RetryableAioHttpClient(
        timeout_in_seconds=0.1,  # Very short timeout
        retries=1,
        use_data_streaming=False,
    ) as client:
        with aioresponses() as m:
            m.get("http://test.com", status=200, body=asyncio.sleep(1))

            with pytest.raises(Exception):
                await client.get(url="http://test.com")
