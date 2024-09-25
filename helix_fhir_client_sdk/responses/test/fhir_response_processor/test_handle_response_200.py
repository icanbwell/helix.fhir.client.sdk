from unittest.mock import AsyncMock, MagicMock
from helix_fhir_client_sdk.responses.fhir_response_processor import (
    FhirResponseProcessor,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_response import (
    RetryableAioHttpResponse,
)
from helix_fhir_client_sdk.loggers.fhir_logger import FhirLogger


async def test_handle_response_200() -> None:
    access_token = "mock_access_token"
    full_url = "http://example.com"
    request_id = "mock_request_id"
    response_headers = ["mock_header"]
    resources_json = ""
    chunk_size = 1024
    extra_context_to_return = {"extra_key": "extra_value"}
    resource = "Patient"
    id_ = "mock_id"
    logger = MagicMock(FhirLogger)
    expand_fhir_bundle = True
    separate_bundle_resources = False
    url = "http://example.com"
    use_data_streaming = False

    response = MagicMock(RetryableAioHttpResponse)
    response.ok = True
    response.status = 200
    response.get_text_async = AsyncMock(
        return_value='{"resourceType": "Bundle", "total": 2, "entry": [{"resource": {"resourceType": "Patient", "id": "1"}}, {"resource": {"resourceType": "Patient", "id": "2"}}]}'
    )

    fn_handle_streaming_chunk = AsyncMock()

    result = [
        r
        async for r in FhirResponseProcessor._handle_response_200(
            access_token=access_token,
            full_url=full_url,
            response=response,
            request_id=request_id,
            response_headers=response_headers,
            resources_json=resources_json,
            fn_handle_streaming_chunk=fn_handle_streaming_chunk,
            use_data_streaming=use_data_streaming,
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

    expected_result = [
        {
            "request_id": request_id,
            "url": full_url,
            "responses": '[{"resourceType": "Patient", "id": "1"}, {"resourceType": "Patient", "id": "2"}]',
            "error": None,
            "access_token": access_token,
            "total_count": 2,
            "status": 200,
            "next_url": None,
            "extra_context_to_return": extra_context_to_return,
            "resource_type": resource,
            "id_": id_,
            "response_headers": response_headers,
            "chunk_number": None,
            "successful": True,
            "cache_hits": None,
        }
    ]

    assert result[0].__dict__ == expected_result[0]
