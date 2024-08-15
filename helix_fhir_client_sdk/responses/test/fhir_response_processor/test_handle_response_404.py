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


async def test_handle_response_404() -> None:
    access_token = "mock_access_token"
    full_url = "http://example.com"
    request_id = "mock_request_id"
    response_headers = ["mock_header"]
    extra_context_to_return = {"extra_key": "extra_value"}
    resource = "Patient"
    id_ = "mock_id"
    logger = MagicMock(FhirLogger)

    response = MagicMock(RetryableAioHttpResponse)
    response.ok = False
    response.status = 404
    response.get_text_async = AsyncMock(return_value="Not Found")

    result: List[FhirGetResponse] = [
        r
        async for r in FhirResponseProcessor._handle_response_404(
            full_url=full_url,
            request_id=request_id,
            response=response,
            response_headers=response_headers,
            access_token=access_token,
            extra_context_to_return=extra_context_to_return,
            resource=resource,
            id_=id_,
            logger=logger,
        )
    ]

    expected_result = [
        {
            "request_id": request_id,
            "chunk_number": None,
            "url": full_url,
            "responses": "Not Found",
            "error": "NotFound",
            "next_url": None,
            "access_token": access_token,
            "total_count": 0,
            "status": 404,
            "extra_context_to_return": extra_context_to_return,
            "resource_type": resource,
            "id_": id_,
            "response_headers": response_headers,
            "successful": False,
            "cache_hits": None,
        }
    ]

    assert result[0].__dict__ == expected_result[0]
