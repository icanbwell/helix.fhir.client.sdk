from unittest.mock import AsyncMock, MagicMock

import pytest

from helix_fhir_client_sdk.utilities.retryable_aiohttp_response import (
    RetryableAioHttpResponse,
)


def _make_response(
    *,
    response_text: str,
    content: MagicMock | None,
    use_data_streaming: bool | None,
) -> RetryableAioHttpResponse:
    return RetryableAioHttpResponse(
        ok=True,
        status=200,
        response_headers={},
        response_text=response_text,
        content=content,
        use_data_streaming=use_data_streaming,
        results_by_url=[],
        access_token=None,
        access_token_expiry_date=None,
        retry_count=0,
    )


@pytest.mark.asyncio
async def test_get_text_async_reads_stream_when_not_yet_consumed() -> None:
    content = MagicMock()
    content.at_eof.return_value = False
    content.read = AsyncMock(return_value=b"streamed body")

    response = _make_response(response_text="", content=content, use_data_streaming=True)

    assert await response.get_text_async() == "streamed body"
    content.read.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_text_async_prefers_captured_text_when_stream_already_drained() -> None:
    """Error responses have their body eagerly read via response.text() before this
    object is constructed, leaving the stream at EOF. Re-reading it would silently
    return an empty error body instead of the real diagnostics (regression test)."""
    content = MagicMock()
    content.at_eof.return_value = True
    content.read = AsyncMock(return_value=b"")

    response = _make_response(response_text="real error body", content=content, use_data_streaming=True)

    assert await response.get_text_async() == "real error body"
    content.read.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_text_async_without_streaming_uses_response_text() -> None:
    content = MagicMock()
    content.at_eof.return_value = False
    content.read = AsyncMock(return_value=b"should not be read")

    response = _make_response(response_text="eager body", content=content, use_data_streaming=False)

    assert await response.get_text_async() == "eager body"
    content.read.assert_not_awaited()


def _make_real_stream_reader_mock(*, body: bytes) -> MagicMock:
    """A real aiohttp StreamReader's at_eof() flips from False to True once read() has
    fully drained it - unlike a mock with a fixed at_eof() return value, which can hide
    caching bugs that only manifest once the stream is genuinely exhausted."""
    content = MagicMock()
    state = {"read": False}
    content.at_eof.side_effect = lambda: state["read"]

    async def _read() -> bytes:
        state["read"] = True
        return body

    content.read = AsyncMock(side_effect=_read)
    return content


@pytest.mark.asyncio
async def test_get_text_async_caches_streamed_text() -> None:
    """Regression test: get_text_async() must cache the streamed body via text_read and
    return it on subsequent calls, even though reading it flips the real StreamReader's
    at_eof() to True - a naive at_eof()-gated cache check would fall back to the (empty)
    _response_text on the second call instead of the cached text."""
    content = _make_real_stream_reader_mock(body=b"once")

    response = _make_response(response_text="", content=content, use_data_streaming=True)

    assert await response.get_text_async() == "once"
    assert await response.get_text_async() == "once"
    content.read.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_text_async_with_no_content_uses_response_text() -> None:
    response = _make_response(response_text="no stream", content=None, use_data_streaming=True)

    assert await response.get_text_async() == "no stream"
