import json

import pytest
from typing import List

from aioresponses import aioresponses

from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource
from helix_fhir_client_sdk.fhir.fhir_resource_list import FhirResourceList
from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.merge.fhir_merge_response_result import (
    FhirMergeResponseResult,
)


@pytest.mark.asyncio
async def test_merge_resources_async_success() -> None:
    """Test successful merge_async call."""
    url = "http://example.com/Patient/1/$merge"
    fhir_merge_mixin = FhirClient().url(url).resource("Patient")
    json_data_list = ['{"resourceType": "Patient", "id": "1"}']
    with aioresponses() as m:
        m.post("http://validation-server.com/Patient/$validate", status=200, payload={})
        m.post(url, status=200, payload={"resourceType": "Patient", "id": "1"})
        fhir_merge_mixin._url = "http://example.com"
        fhir_merge_mixin._resource = "Patient"
        fhir_merge_mixin._validation_server_url = "http://validation-server.com"

        responses: List[FhirMergeResponseResult] = [
            response
            async for response in fhir_merge_mixin.merge_resources_async(
                resources_to_merge=FhirResourceList(
                    [FhirResource(json.loads(o)) for o in json_data_list]
                )
            )
        ]

        assert len(responses) == 1
        assert responses[0].status == 200
        assert responses[0].responses[0].resource_type == "Patient"


@pytest.mark.asyncio
async def test_merge_resources_async_validation_error() -> None:
    """Test merge_async call with validation errors."""
    url = "http://example.com/Patient/1/$merge"
    fhir_merge_mixin = FhirClient().url(url).resource("Patient")
    json_data_list = ['{"resourceType": "Patient", "id": "1"}']
    fhir_merge_mixin._validation_server_url = "http://validation-server.com"

    with aioresponses() as m:
        m.post(
            "http://validation-server.com/Patient/$validate",
            status=400,
            payload={"issue": [{"severity": "error", "code": "invalid"}]},
        )

        responses: List[FhirMergeResponseResult] = [
            response
            async for response in fhir_merge_mixin.merge_resources_async(
                resources_to_merge=FhirResourceList(
                    [FhirResource(json.loads(o)) for o in json_data_list]
                )
            )
        ]

        assert len(responses) == 1
        assert responses[0].status == 500
        issue = responses[0].responses[0].issue
        assert issue is not None
        assert issue[0]["code"] == "invalid"


@pytest.mark.asyncio
async def test_merge_async_http_error() -> None:
    """Test merge_async call with HTTP errors."""
    url = "http://example.com/Patient/1/$merge"
    fhir_merge_mixin = (
        FhirClient().url(url).resource("Patient").throw_exception_on_error(False)
    )

    json_data_list = ['{"resourceType": "Patient", "id": "1"}']

    with aioresponses() as m:
        m.post(
            "http://example.com/Patient/1/$merge",
            status=500,
            payload={"issue": [{"severity": "error", "code": "exception"}]},
        )

        responses: List[FhirMergeResponseResult] = [
            response
            async for response in fhir_merge_mixin.merge_resources_async(
                resources_to_merge=FhirResourceList(
                    [FhirResource(json.loads(o)) for o in json_data_list]
                )
            )
        ]

        assert len(responses) == 1
        assert responses[0].status == 500
        issue = responses[0].responses[0].issue
        assert issue is not None
        assert issue[0]["code"] == "exception"


@pytest.mark.asyncio
async def test_validate_content_success() -> None:
    """Test successful validation of content."""
    url = "http://example.com/Patient/1/$merge"
    fhir_merge_mixin = FhirClient().url(url).resource("Patient")

    json_data_list = [{"resourceType": "Patient", "id": "1"}]
    fhir_merge_mixin._validation_server_url = "http://validation-server.com"

    with aioresponses() as m:
        m.post("http://validation-server.com/Patient/$validate", status=200, payload={})

        clean_resources, errors = await fhir_merge_mixin.validate_resource(
            resources_to_validate=FhirResourceList(
                [FhirResource(o) for o in json_data_list]
            )
        )

        assert len(clean_resources) == 1
        assert len(errors) == 0


@pytest.mark.asyncio
async def test_validate_content_error() -> None:
    """Test validation of content with errors."""
    url = "http://example.com/Patient/1/$merge"
    fhir_merge_mixin = FhirClient().url(url).resource("Patient")

    json_data_list = [{"resourceType": "Patient", "id": "1"}]
    fhir_merge_mixin._validation_server_url = "http://validation-server.com"

    with aioresponses() as m:
        m.post(
            "http://validation-server.com/Patient/$validate",
            status=400,
            payload={"issue": [{"severity": "error", "code": "invalid"}]},
        )

        clean_resources, errors = await fhir_merge_mixin.validate_resource(
            resources_to_validate=FhirResourceList(
                [FhirResource(o) for o in json_data_list]
            )
        )

        assert len(clean_resources) == 0
        assert len(errors) == 1
        issue = errors[0].issue
        assert issue is not None
        assert issue[0]["code"] == "invalid"
