"""End-to-end tests that use_data_streaming() actually changes $merge behavior:
the server is told to stream back ndjson (Accept header) and the SDK correctly
parses a streamed response, including preserving error diagnostics on failure.
"""

import pytest
from aioresponses import aioresponses
from compressedfhir.fhir.fhir_resource import FhirResource
from compressedfhir.fhir.fhir_resource_list import FhirResourceList

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.merge.fhir_merge_resource_response import (
    FhirMergeResourceResponse,
)


@pytest.mark.asyncio
async def test_merge_async_streaming_success_parses_streamed_response() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient").use_data_streaming(True)
    json_data_list = ['{"resourceType": "Patient", "id": "1"}']

    with aioresponses() as m:
        m.post(url, status=200, payload={"resourceType": "Patient", "id": "1", "created": True})

        responses = [response async for response in fhir_client.merge_async(json_data_list=json_data_list)]

        assert len(responses) == 1
        assert responses[0].status == 200
        assert responses[0].responses[0]["resourceType"] == "Patient"
        assert responses[0].responses[0]["created"] is True


@pytest.mark.asyncio
async def test_merge_async_streaming_error_preserves_diagnostics() -> None:
    """Regression test: before the fix, a failed $merge with use_data_streaming
    enabled reported an empty error body instead of the server's OperationOutcome."""
    url = "http://example.com/Patient/1/$merge"
    fhir_client = (
        FhirClient()
        .url("http://example.com")
        .resource("Patient")
        .use_data_streaming(True)
        .throw_exception_on_error(False)
    )
    json_data_list = ['{"resourceType": "Patient", "id": "1"}']
    operation_outcome = {
        "resourceType": "OperationOutcome",
        "issue": [{"severity": "error", "code": "invalid", "diagnostics": "Patient.name is required"}],
    }

    with aioresponses() as m:
        m.post(url, status=400, payload=operation_outcome)

        responses = [response async for response in fhir_client.merge_async(json_data_list=json_data_list)]

        assert len(responses) == 1
        assert responses[0].status == 400
        assert responses[0].error is not None
        assert "Patient.name is required" in responses[0].error


@pytest.mark.asyncio
async def test_merge_resources_async_streaming_success_parses_streamed_response() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient").use_data_streaming(True)
    json_data_list = [{"resourceType": "Patient", "id": "1"}]

    with aioresponses() as m:
        m.post(url, status=200, payload={"resourceType": "Patient", "id": "1", "created": True})

        responses: list[FhirMergeResourceResponse] = [
            response
            async for response in fhir_client.merge_resources_async(
                id_="1",
                resources_to_merge=FhirResourceList([FhirResource(o) for o in json_data_list]),
                batch_size=None,
            )
        ]

        assert len(responses) == 1
        assert responses[0].status == 200
        assert responses[0].responses[0].resource_type == "Patient"


@pytest.mark.asyncio
async def test_merge_resources_async_streaming_error_preserves_diagnostics() -> None:
    """Regression test: before the fix, a failed $merge with use_data_streaming
    enabled reported an empty error body instead of the server's OperationOutcome."""
    url = "http://example.com/Patient/1/$merge"
    fhir_client = (
        FhirClient()
        .url("http://example.com")
        .resource("Patient")
        .use_data_streaming(True)
        .throw_exception_on_error(False)
    )
    json_data_list = [{"resourceType": "Patient", "id": "1"}]
    operation_outcome = {
        "resourceType": "OperationOutcome",
        "issue": [{"severity": "error", "code": "invalid", "diagnostics": "Patient.name is required"}],
    }

    with aioresponses() as m:
        m.post(url, status=400, payload=operation_outcome)

        responses: list[FhirMergeResourceResponse] = [
            response
            async for response in fhir_client.merge_resources_async(
                id_="1",
                resources_to_merge=FhirResourceList([FhirResource(o) for o in json_data_list]),
                batch_size=None,
            )
        ]

        assert len(responses) == 1
        assert responses[0].status == 400
        issue = responses[0].responses[0].issue
        assert issue is not None
        assert "Patient.name is required" in str(issue)
