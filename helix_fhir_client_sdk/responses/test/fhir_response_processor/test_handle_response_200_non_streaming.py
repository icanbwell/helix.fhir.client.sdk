from typing import List
from unittest.mock import AsyncMock, MagicMock

from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.fhir_response_processor import (
    FhirResponseProcessor,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_response import (
    RetryableAioHttpResponse,
)
from helix_fhir_client_sdk.loggers.fhir_logger import FhirLogger


async def test_handle_response_200_non_streaming() -> None:
    access_token = "mock_access_token"
    full_url = "http://example.com"
    request_id = "mock_request_id"
    response_headers = ["mock_header"]
    resources_json = ""
    next_url = None
    total_count = 0
    logger = MagicMock(FhirLogger)
    expand_fhir_bundle = True
    separate_bundle_resources = False
    extra_context_to_return = {"extra_key": "extra_value"}
    resource = "Patient"
    id_ = "mock_id"
    url = "http://example.com"

    response = MagicMock(RetryableAioHttpResponse)
    response.ok = True
    response.status = 200
    response.get_text_async = AsyncMock(
        return_value='{"resourceType": "Bundle", "total": 2, "entry": [{"resource": {"resourceType": "Patient", "id": "1"}}, {"resource": {"resourceType": "Patient", "id": "2"}}]}'
    )

    result: List[FhirGetResponse] = [
        r
        async for r in FhirResponseProcessor._handle_response_200_non_streaming(
            access_token=access_token,
            full_url=full_url,
            response=response,
            request_id=request_id,
            response_headers=response_headers,
            resources_json=resources_json,
            next_url=next_url,
            total_count=total_count,
            logger=logger,
            expand_fhir_bundle=expand_fhir_bundle,
            separate_bundle_resources=separate_bundle_resources,
            extra_context_to_return=extra_context_to_return,
            resource=resource,
            id_=id_,
            url=url,
        )
    ]

    assert len(result) == 1

    expected_result = {
        "request_id": request_id,
        "chunk_number": None,
        "url": full_url,
        "responses": '[{"resourceType": "Patient", "id": "1"}, {"resourceType": "Patient", "id": "2"}]',
        "error": None,
        "access_token": access_token,
        "total_count": 2,
        "status": 200,
        "next_url": next_url,
        "extra_context_to_return": extra_context_to_return,
        "resource_type": resource,
        "id_": id_,
        "successful": True,
        "response_headers": response_headers,
        "cache_hits": None,
    }

    assert result[0].__dict__ == expected_result
