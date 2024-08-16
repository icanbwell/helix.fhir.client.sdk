import pytest
import json
from datetime import datetime

from helix_fhir_client_sdk.fhir_bundle import (
    Bundle,
    BundleEntry,
    BundleEntryRequest,
    BundleEntryResponse,
)
from helix_fhir_client_sdk.fhir_bundle_appender import FhirBundleAppender
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


@pytest.fixture
def fhir_get_response() -> FhirGetResponse:
    """Fixture for FhirGetResponse instance."""
    return FhirGetResponse(
        url="http://example.com/resource/1",
        resource_type="Patient",
        id_="1",
        status=200,
        responses=json.dumps({"resourceType": "Patient", "id": "1"}),
        error=None,
        access_token="test_token",
        request_id="1234",
        extra_context_to_return={"context_key": "context_value"},
        total_count=1,
        response_headers=["Content-Type:application/json"],
    )


@pytest.fixture
def error_fhir_get_response() -> FhirGetResponse:
    """Fixture for FhirGetResponse instance with an error."""
    return FhirGetResponse(
        url="http://example.com/resource/2",
        resource_type="Patient",
        id_="2",
        status=404,
        responses="",
        error="Resource not found",
        access_token="test_token",
        request_id="5678",
        total_count=1,
        response_headers=["Content-Type:application/json"],
        extra_context_to_return={"context_key": "context_value"},
    )


@pytest.fixture
def bundle() -> Bundle:
    """Fixture for Bundle instance."""
    return Bundle(entry=[])


def test_append_responses_success(
    fhir_get_response: FhirGetResponse, bundle: Bundle
) -> None:
    """Test appending successful responses to the bundle."""
    bundle = FhirBundleAppender.append_responses(
        responses=[fhir_get_response], bundle=bundle
    )

    assert bundle.entry is not None
    assert len(bundle.entry) == 1
    assert bundle.entry[0].resource == {"resourceType": "Patient", "id": "1"}
    assert bundle.entry[0].request is not None
    assert bundle.entry[0].request.url == "http://example.com/resource/1"
    assert bundle.entry[0].response is not None
    assert bundle.entry[0].response.status == "200"


def test_append_responses_error(
    error_fhir_get_response: FhirGetResponse, bundle: Bundle
) -> None:
    """Test appending error responses to the bundle."""
    bundle = FhirBundleAppender.append_responses(
        responses=[error_fhir_get_response], bundle=bundle
    )

    assert bundle.entry is not None
    assert len(bundle.entry) == 1
    assert bundle.entry[0].resource is not None
    assert bundle.entry[0].resource["resourceType"] == "OperationOutcome"
    assert bundle.entry[0].resource["issue"][0]["severity"] == "error"
    assert bundle.entry[0].resource["issue"][0]["code"] == "not-found"
    assert bundle.entry[0].request is not None
    assert bundle.entry[0].request.url == "http://example.com/resource/2"
    assert bundle.entry[0].response is not None
    assert bundle.entry[0].response.status == "404"


def test_remove_duplicate_resources() -> None:
    """Test removing duplicate resources from the bundle."""
    bundle = Bundle(
        entry=[
            BundleEntry(
                resource={"resourceType": "Patient", "id": "1"},
                request=BundleEntryRequest(url="http://example.com/resource/1"),
                response=BundleEntryResponse(
                    status="200", lastModified=datetime(2023, 8, 14), etag="67890"
                ),
            ),
            BundleEntry(
                resource={"resourceType": "Patient", "id": "1"},
                request=BundleEntryRequest(url="http://example.com/resource/1"),
                response=BundleEntryResponse(
                    status="200", lastModified=datetime(2023, 8, 14), etag="67890"
                ),
            ),
            BundleEntry(
                resource={"resourceType": "Patient", "id": "2"},
                request=BundleEntryRequest(url="http://example.com/resource/2"),
                response=BundleEntryResponse(
                    status="200", lastModified=datetime(2023, 8, 14), etag="12345"
                ),
            ),
        ]
    )

    bundle = FhirBundleAppender.remove_duplicate_resources(bundle=bundle)

    assert bundle.entry is not None
    assert len(bundle.entry) == 2
    assert bundle.entry[0].resource is not None
    assert bundle.entry[0].resource["id"] == "1"
    assert bundle.entry[1].resource is not None
    assert bundle.entry[1].resource["id"] == "2"
