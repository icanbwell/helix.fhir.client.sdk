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

# Synthetic resources (no PHI).
FIRST: dict[str, Any] = {"resourceType": "Patient", "id": "1"}
LAST: dict[str, Any] = {"resourceType": "Patient", "id": "2"}


async def _stream(chunk_text: str, byte_identical_json: bool) -> list[FhirGetResponse]:
    response = MagicMock(RetryableAioHttpResponse)
    response.ok = True
    response.status = 200
    response.results_by_url = []
    response.content = MagicMock()

    async def iterator(chunk_size: int) -> AsyncGenerator[bytes, None]:
        yield chunk_text.encode("utf-8")

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


@pytest.mark.parametrize("bad_line", ["{bad", '{"id": NaN}', "[" * 1100 + "]" * 1100])
async def test_invalid_line_yields_the_lines_before_it_then_an_error_response(bad_line: str) -> None:
    chunk_text = f"{json.dumps(FIRST)}\n{bad_line}\n{json.dumps(LAST)}\n"

    results = await _stream(chunk_text, byte_identical_json=False)

    assert [r.status for r in results] == [200, 200]
    assert results[0].error is None
    assert json.loads(results[0].get_response_text()) == FIRST
    assert results[1].error is not None


async def test_byte_identical_json_keeps_lines_the_standard_library_accepts() -> None:
    chunk_text = f'{json.dumps(FIRST)}\n{{"id": NaN}}\n{json.dumps(LAST)}\n'

    results = await _stream(chunk_text, byte_identical_json=True)

    assert len(results) == 3
    assert all(r.error is None for r in results)
