import json
from collections.abc import AsyncGenerator
from logging import Logger
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)

from helix_fhir_client_sdk.responses.fhir_response_processor import (
    FhirResponseProcessor,
)
from helix_fhir_client_sdk.utilities.ndjson_chunk_streaming_parser import (
    NdJsonChunkStreamingParser,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_response import (
    RetryableAioHttpResponse,
)


async def test_handle_response_200_streaming() -> None:
    access_token = "mock_access_token"
    full_url = "http://example.com"
    request_id = "mock_request_id"
    chunk_size = 1024
    extra_context_to_return = {"extra_key": "extra_value"}
    resource_type = "Patient"
    id_ = "mock_id"
    logger = MagicMock(Logger)
    expand_fhir_bundle = False
    separate_bundle_resources = False
    url = "http://example.com"

    response = MagicMock(RetryableAioHttpResponse)
    response.ok = True
    response.status = 200
    response.results_by_url = []
    response.content = MagicMock()

    patient: dict[str, Any] = {"resourceType": "Patient", "id": "1"}

    # Define an async iterator
    async def async_iterator(chunk_size1: int) -> AsyncGenerator[bytes, None]:
        patient_text: str = json.dumps(patient)
        yield b"%s\n" % patient_text.encode("utf-8")  # Simulating a chunk of data

    response.content.iter_chunked = async_iterator
    response.content.at_eof = MagicMock(return_value=False)  # Mocking the at_eof method to return False

    response.response_headers = {"mock_header": "mock_value"}

    fn_handle_streaming_chunk = AsyncMock()
    nd_json_chunk_streaming_parser = NdJsonChunkStreamingParser()

    result = [
        r
        async for r in FhirResponseProcessor._handle_response_200_streaming(
            access_token=access_token,
            fn_handle_streaming_chunk=fn_handle_streaming_chunk,
            full_url=full_url,
            nd_json_chunk_streaming_parser=nd_json_chunk_streaming_parser,
            next_url=None,
            request_id=request_id,
            response=response,
            response_headers=["mock_header=mock_value"],
            total_count=0,
            chunk_size=chunk_size,
            extra_context_to_return=extra_context_to_return,
            resource=resource_type,
            id_=id_,
            logger=logger,
            expand_fhir_bundle=expand_fhir_bundle,
            separate_bundle_resources=separate_bundle_resources,
            url=url,
            storage_mode=CompressedDictStorageMode(),
            create_operation_outcome_for_error=False,
        )
    ]

    assert len(result) == 1

    expected_result = [
        {
            "request_id": request_id,
            "url": full_url,
            "_resource": patient,
            "error": None,
            "access_token": access_token,
            "total_count": 0,
            "status": 200,
            "next_url": None,
            "extra_context_to_return": extra_context_to_return,
            "resource_type": resource_type,
            "id_": id_,
            "response_headers": ["mock_header=mock_value"],
            "chunk_number": 1,
            "cache_hits": None,
            "results_by_url": [],
            "storage_type": "compressed",
        }
    ]

    assert result[0].to_dict() == expected_result[0]
