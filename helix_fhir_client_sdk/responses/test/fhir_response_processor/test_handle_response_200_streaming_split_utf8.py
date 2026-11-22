import json
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)

from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.fhir_response_processor import (
    FhirResponseProcessor,
)
from helix_fhir_client_sdk.utilities.ndjson_chunk_streaming_parser import (
    NdJsonChunkStreamingParser,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_response import (
    RetryableAioHttpResponse,
)

# Synthetic resource (no PHI); the name holds 2-, 3- and 4-byte UTF-8 characters.
RESOURCE: dict[str, Any] = {"resourceType": "Patient", "id": "1", "name": [{"family": "é€😀"}]}


async def _stream(chunks: list[bytes], byte_identical_json: bool) -> list[FhirGetResponse]:
    response = MagicMock(RetryableAioHttpResponse)
    response.ok = True
    response.status = 200
    response.results_by_url = []
    response.content = MagicMock()

    async def iterator(chunk_size: int) -> AsyncGenerator[bytes, None]:
        for chunk in chunks:
            yield chunk

    response.content.iter_chunked = iterator
    response.content.at_eof = MagicMock(return_value=False)
    response.response_headers = {}

    return [
        r
        async for r in FhirResponseProcessor._handle_response_200_streaming(
            access_token=None,
            fn_handle_streaming_chunk=AsyncMock(),
            full_url="http://example.com",
            nd_json_chunk_streaming_parser=NdJsonChunkStreamingParser(byte_identical_json=byte_identical_json),
            next_url=None,
            request_id="request-1",
            response=response,
            response_headers=[],
            total_count=0,
            chunk_size=1024,
            extra_context_to_return=None,
            resource="Patient",
            id_=None,
            logger=None,
            expand_fhir_bundle=False,
            separate_bundle_resources=False,
            url="http://example.com",
            storage_mode=CompressedDictStorageMode(),
            byte_identical_json=byte_identical_json,
            create_operation_outcome_for_error=False,
        )
    ]


def _line_bytes() -> bytes:
    return (json.dumps(RESOURCE, ensure_ascii=False) + "\n").encode("utf-8")


# every split offset inside a multi-byte character of the record
_SPLIT_OFFSETS = [i for i, b in enumerate(_line_bytes()) if i > 0 and (b & 0xC0) == 0x80]


@pytest.mark.parametrize("byte_identical_json", [False, True])
@pytest.mark.parametrize("offset", _SPLIT_OFFSETS)
@pytest.mark.asyncio
async def test_multibyte_character_split_across_chunks_is_delivered_intact(
    offset: int, byte_identical_json: bool
) -> None:
    data = _line_bytes()

    results = await _stream([data[:offset], data[offset:]], byte_identical_json)

    assert [r.error for r in results] == [None]
    assert json.loads(results[0].get_response_text()) == RESOURCE


@pytest.mark.parametrize("byte_identical_json", [False, True])
@pytest.mark.asyncio
async def test_stream_ending_inside_a_multibyte_character_yields_an_error_response(
    byte_identical_json: bool,
) -> None:
    data = _line_bytes()

    results = await _stream([data[: _SPLIT_OFFSETS[0]]], byte_identical_json)

    assert results[-1].error is not None


@pytest.mark.asyncio
async def test_invalid_utf8_bytes_yield_an_error_response() -> None:
    results = await _stream([b'{"id": "\xff"}\n'], byte_identical_json=False)

    assert [r.error is not None for r in results] == [True]
