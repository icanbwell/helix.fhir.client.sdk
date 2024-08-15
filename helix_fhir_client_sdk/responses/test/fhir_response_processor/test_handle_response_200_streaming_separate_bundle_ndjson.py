import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
from helix_fhir_client_sdk.responses.fhir_response_processor import (
    FhirResponseProcessor,
)
from helix_fhir_client_sdk.utilities.ndjson_chunk_streaming_parser import (
    NdJsonChunkStreamingParser,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_response import (
    RetryableAioHttpResponse,
)
from helix_fhir_client_sdk.loggers.fhir_logger import FhirLogger


async def test_handle_response_200_streaming_separate_bundle_ndjson() -> None:
    access_token = "mock_access_token"
    full_url = "http://example.com"
    request_id = "mock_request_id"
    chunk_size = 1024
    extra_context_to_return = {"extra_key": "extra_value"}
    resource = "Patient"
    id_ = "mock_id"
    logger = MagicMock(FhirLogger)
    expand_fhir_bundle = True
    separate_bundle_resources = True
    url = "http://example.com"

    response = MagicMock(RetryableAioHttpResponse)
    response.ok = True
    response.status = 200
    response.content = MagicMock()

    # Define an async iterator
    async def async_iterator(chunk_size1: int) -> AsyncGenerator[bytes, None]:
        yield b'{"resourceType": "Practitioner", "id": "1", "contained":[{"resourceType": "PractitionerRole", "id": "2"}]}\n{"resourceType": "Practitioner", "id": "3"}\n'

    response.content.iter_chunked = async_iterator

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
            total_count=3,
            chunk_size=chunk_size,
            extra_context_to_return=extra_context_to_return,
            resource=resource,
            id_=id_,
            logger=logger,
            expand_fhir_bundle=expand_fhir_bundle,
            separate_bundle_resources=separate_bundle_resources,
            url=url,
        )
    ]

    expected_resources = [
        {
            "practitioner": [{"resourceType": "Practitioner", "id": "1"}],
            "practitionerrole": [{"resourceType": "PractitionerRole", "id": "2"}],
            "token": "mock_access_token",
            "url": "http://example.com",
            "extra_key": "extra_value",
        },
        {
            "practitioner": [{"resourceType": "Practitioner", "id": "3"}],
            "token": "mock_access_token",
            "url": "http://example.com",
            "extra_key": "extra_value",
        },
    ]

    assert len(result) == 2

    expected_result = [
        {
            "request_id": request_id,
            "url": full_url,
            "responses": json.dumps([expected_resources[0]]),
            "error": None,
            "access_token": access_token,
            "total_count": 2,
            "status": 200,
            "next_url": None,
            "extra_context_to_return": extra_context_to_return,
            "resource_type": resource,
            "id_": id_,
            "response_headers": ["mock_header=mock_value"],
            "chunk_number": 1,
            "successful": True,
            "cache_hits": None,
        },
        {
            "request_id": request_id,
            "url": full_url,
            "responses": json.dumps([expected_resources[1]]),
            "error": None,
            "access_token": access_token,
            "total_count": 1,
            "status": 200,
            "next_url": None,
            "extra_context_to_return": extra_context_to_return,
            "resource_type": resource,
            "id_": id_,
            "response_headers": ["mock_header=mock_value"],
            "chunk_number": 1,
            "successful": True,
            "cache_hits": None,
        },
    ]

    assert [r.to_dict() for r in result] == expected_result
