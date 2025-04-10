import json
from typing import List, Any, Dict
from unittest.mock import AsyncMock, MagicMock

from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.fhir_response_processor import (
    FhirResponseProcessor,
)
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_response import (
    RetryableAioHttpResponse,
)
from logging import Logger


async def test_handle_response_200_non_streaming_separate_bundle() -> None:
    access_token = "mock_access_token"
    full_url = "http://example.com"
    request_id = "mock_request_id"
    response_headers = ["mock_header"]
    resources_json = ""
    next_url = None
    total_count = 0
    logger = MagicMock(Logger)
    expand_fhir_bundle = True
    separate_bundle_resources = True
    extra_context_to_return = {"extra_key": "extra_value"}
    resource = "Patient"
    id_ = "mock_id"
    url = "http://example.com"

    bundle: Dict[str, Any] = {
        "resourceType": "Bundle",
        "total": 2,
        "entry": [
            {
                "resource": {
                    "resourceType": "Practitioner",
                    "id": "1",
                    "contained": [{"resourceType": "PractitionerRole", "id": "2"}],
                }
            },
            {"resource": {"resourceType": "Practitioner", "id": "3"}},
        ],
    }

    response = MagicMock(RetryableAioHttpResponse)
    response.ok = True
    response.status = 200
    response.results_by_url = []
    response.get_text_async = AsyncMock(return_value=json.dumps(bundle))

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
            storage_mode=CompressedDictStorageMode(),
            create_operation_outcome_for_error=False,
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

    expected_result = {
        "_resources": [
            {
                "extra_key": "extra_value",
                "practitioner": [{"id": "1", "resourceType": "Practitioner"}],
                "practitionerrole": [{"id": "2", "resourceType": "PractitionerRole"}],
                "token": "mock_access_token",
                "url": "http://example.com",
            },
            {
                "extra_key": "extra_value",
                "practitioner": [{"id": "3", "resourceType": "Practitioner"}],
                "token": "mock_access_token",
                "url": "http://example.com",
            },
        ],
        "access_token": "mock_access_token",
        "cache_hits": None,
        "chunk_number": None,
        "error": None,
        "extra_context_to_return": {"extra_key": "extra_value"},
        "id_": "mock_id",
        "next_url": None,
        "request_id": "mock_request_id",
        "resource_type": "Patient",
        "response_headers": ["mock_header"],
        "results_by_url": [],
        "status": 200,
        "total_count": 3,
        "url": "http://example.com",
        "storage_type": "compressed",
    }

    assert result[0].to_dict() == expected_result
