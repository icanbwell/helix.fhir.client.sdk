import pytest
from datetime import datetime

from helix_fhir_client_sdk.fhir_bundle import (
    BundleEntryRequest,
    BundleEntryResponse,
    BundleEntry,
    Bundle,
)


@pytest.fixture
def bundle_entry_request() -> BundleEntryRequest:
    """Fixture for BundleEntryRequest instance."""
    return BundleEntryRequest(
        url="http://example.com/resource",
        method="POST",
        ifNoneMatch="12345",
        ifModifiedSince=datetime(2023, 8, 14),
    )


@pytest.fixture
def bundle_entry_response() -> BundleEntryResponse:
    """Fixture for BundleEntryResponse instance."""
    return BundleEntryResponse(
        status="200",
        etag="67890",
        lastModified=datetime(2023, 8, 14),
    )


@pytest.fixture
def bundle_entry(
    bundle_entry_request: BundleEntryRequest, bundle_entry_response: BundleEntryResponse
) -> BundleEntry:
    """Fixture for BundleEntry instance."""
    return BundleEntry(
        fullUrl="http://example.com/resource/1",
        resource={"id": "1", "resourceType": "Patient"},
        request=bundle_entry_request,
        response=bundle_entry_response,
    )


@pytest.fixture
def bundle(bundle_entry: BundleEntry) -> Bundle:
    """Fixture for Bundle instance."""
    return Bundle(entry=[bundle_entry])


def test_bundle_entry_request_to_dict(bundle_entry_request: BundleEntryRequest) -> None:
    """Test converting BundleEntryRequest to dict."""
    expected_dict = {
        "url": "http://example.com/resource",
        "method": "POST",
        "ifNoneMatch": "12345",
        "ifModifiedSince": "2023-08-14T00:00:00",
    }
    assert bundle_entry_request.to_dict() == expected_dict


def test_bundle_entry_request_from_dict() -> None:
    """Test creating BundleEntryRequest from dict."""
    data = {
        "url": "http://example.com/resource",
        "method": "POST",
        "ifNoneMatch": "12345",
        "ifModifiedSince": "2023-08-14T00:00:00",
    }
    bundle_entry_request = BundleEntryRequest.from_dict(data)
    assert bundle_entry_request.url == "http://example.com/resource"
    assert bundle_entry_request.method == "POST"
    assert bundle_entry_request.ifNoneMatch == "12345"
    assert bundle_entry_request.ifModifiedSince == datetime(2023, 8, 14)


def test_bundle_entry_response_to_dict(
    bundle_entry_response: BundleEntryResponse,
) -> None:
    """Test converting BundleEntryResponse to dict."""
    expected_dict = {
        "status": "200",
        "etag": "67890",
        "lastModified": "2023-08-14T00:00:00",
    }
    assert bundle_entry_response.to_dict() == expected_dict


def test_bundle_entry_response_from_dict() -> None:
    """Test creating BundleEntryResponse from dict."""
    data = {
        "status": "200",
        "etag": "67890",
        "lastModified": "2023-08-14T00:00:00",
    }
    bundle_entry_response = BundleEntryResponse.from_dict(data)
    assert bundle_entry_response.status == "200"
    assert bundle_entry_response.etag == "67890"
    assert bundle_entry_response.lastModified == datetime(2023, 8, 14)


def test_bundle_entry_to_dict(bundle_entry: BundleEntry) -> None:
    """Test converting BundleEntry to dict."""
    expected_dict = {
        "fullUrl": "http://example.com/resource/1",
        "resource": {"id": "1", "resourceType": "Patient"},
        "request": {
            "url": "http://example.com/resource",
            "method": "POST",
            "ifNoneMatch": "12345",
            "ifModifiedSince": "2023-08-14T00:00:00",
        },
        "response": {
            "status": "200",
            "etag": "67890",
            "lastModified": "2023-08-14T00:00:00",
        },
    }
    assert bundle_entry.to_dict() == expected_dict


def test_bundle_entry_from_dict() -> None:
    """Test creating BundleEntry from dict."""
    data = {
        "fullUrl": "http://example.com/resource/1",
        "resource": {"id": "1", "resourceType": "Patient"},
        "request": {
            "url": "http://example.com/resource",
            "method": "POST",
            "ifNoneMatch": "12345",
            "ifModifiedSince": "2023-08-14T00:00:00",
        },
        "response": {
            "status": "200",
            "etag": "67890",
            "lastModified": "2023-08-14T00:00:00",
        },
    }
    bundle_entry = BundleEntry.from_dict(data)
    assert bundle_entry.fullUrl == "http://example.com/resource/1"
    assert bundle_entry.resource == {"id": "1", "resourceType": "Patient"}
    assert bundle_entry.request is not None
    assert bundle_entry.request.url == "http://example.com/resource"
    assert bundle_entry.response is not None
    assert bundle_entry.response.status == "200"


def test_bundle_to_dict(bundle: Bundle) -> None:
    """Test converting Bundle to dict."""
    expected_dict = {
        "entry": [
            {
                "fullUrl": "http://example.com/resource/1",
                "resource": {"id": "1", "resourceType": "Patient"},
                "request": {
                    "url": "http://example.com/resource",
                    "method": "POST",
                    "ifNoneMatch": "12345",
                    "ifModifiedSince": "2023-08-14T00:00:00",
                },
                "response": {
                    "status": "200",
                    "etag": "67890",
                    "lastModified": "2023-08-14T00:00:00",
                },
            }
        ]
    }
    assert bundle.to_dict() == expected_dict


def test_bundle_add_diagnostics_to_operation_outcomes() -> None:
    """Test adding diagnostics to OperationOutcome resource."""
    resource = {
        "resourceType": "OperationOutcome",
        "issue": [
            {"details": {"coding": [{"system": "http://example.com", "code": "123"}]}}
        ],
    }
    diagnostics_coding = [{"system": "http://example.com", "code": "456"}]

    updated_resource = Bundle.add_diagnostics_to_operation_outcomes(
        resource=resource, diagnostics_coding=diagnostics_coding
    )

    expected_resource = {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "details": {
                    "coding": [
                        {"system": "http://example.com", "code": "123"},
                        {"system": "http://example.com", "code": "456"},
                    ]
                }
            }
        ],
    }

    assert updated_resource == expected_resource
