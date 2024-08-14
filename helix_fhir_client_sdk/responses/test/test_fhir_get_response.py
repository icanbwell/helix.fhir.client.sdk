import json
from datetime import datetime
from typing import List

from helix_fhir_client_sdk.fhir_bundle import BundleEntry
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse

# Sample data for testing
sample_response = {
    "resourceType": "Bundle",
    "entry": [
        {
            "resource": {
                "resourceType": "Patient",
                "id": "1",
                "name": [{"family": "Doe", "given": ["John"]}],
            }
        },
        {
            "resource": {
                "resourceType": "Patient",
                "id": "2",
                "name": [{"family": "Smith", "given": ["Jane"]}],
            }
        },
    ],
}


# Helper function to create a FhirGetResponse instance
def create_fhir_get_response(responses: str) -> FhirGetResponse:
    return FhirGetResponse(
        request_id="123",
        url="http://example.com",
        responses=responses,
        error=None,
        access_token="token",
        total_count=2,
        status=200,
        next_url=None,
        extra_context_to_return=None,
        resource_type="Patient",
        id_=["1", "2"],
        response_headers=[
            "Last-Modified: Wed, 21 Oct 2015 07:28:00 GMT",
            'ETag: W/"123"',
        ],
        chunk_number=1,
    )


# Test for get_resources method
def test_get_resources() -> None:
    fhir_response = create_fhir_get_response(json.dumps(sample_response))
    resources = fhir_response.get_resources()
    assert len(resources) == 2
    assert resources[0]["resourceType"] == "Patient"
    assert resources[0]["id"] == "1"


# Test for get_bundle_entries method
def test_get_bundle_entries() -> None:
    fhir_response = create_fhir_get_response(json.dumps(sample_response))
    bundle_entries: List[BundleEntry] = fhir_response.get_bundle_entries()
    assert len(bundle_entries) == 2
    assert bundle_entries[0].resource
    assert bundle_entries[0].resource["id"] == "1"


# Test for remove_duplicates method
def test_remove_duplicates() -> None:
    duplicate_response = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "1",
                    "name": [{"family": "Doe", "given": ["John"]}],
                }
            },
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "1",
                    "name": [{"family": "Doe", "given": ["John"]}],
                }
            },
        ],
    }
    fhir_response = create_fhir_get_response(json.dumps(duplicate_response))
    fhir_response.remove_duplicates()
    resources = fhir_response.get_resources()
    assert len(resources) == 1
    assert resources[0]["id"] == "1"


# Test for get_resource_type_and_ids method
def test_get_resource_type_and_ids() -> None:
    fhir_response = create_fhir_get_response(json.dumps(sample_response))
    resource_ids = fhir_response.get_resource_type_and_ids()
    assert len(resource_ids) == 2
    assert resource_ids[0] == "Patient/1"


# Test for lastModified property
def test_last_modified() -> None:
    fhir_response = create_fhir_get_response(json.dumps(sample_response))
    last_modified = fhir_response.lastModified
    assert last_modified == datetime(2015, 10, 21, 7, 0)


# Test for etag property
def test_etag() -> None:
    fhir_response = create_fhir_get_response(json.dumps(sample_response))
    etag = fhir_response.etag
    assert etag == 'W/"123"'


# Test for get_operation_outcomes method
def test_get_operation_outcomes() -> None:
    operation_outcome_response = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "OperationOutcome",
                    "id": "1",
                    "issue": [
                        {
                            "severity": "error",
                            "code": "exception",
                            "diagnostics": "Error",
                        }
                    ],
                }
            }
        ],
    }
    fhir_response = create_fhir_get_response(json.dumps(operation_outcome_response))
    outcomes = fhir_response.get_operation_outcomes()
    assert len(outcomes) == 1
    assert outcomes[0]["resourceType"] == "OperationOutcome"


# Test for get_resources_except_operation_outcomes method
def test_get_resources_except_operation_outcomes() -> None:
    mixed_response = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "OperationOutcome",
                    "id": "1",
                    "issue": [
                        {
                            "severity": "error",
                            "code": "exception",
                            "diagnostics": "Error",
                        }
                    ],
                }
            },
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "2",
                    "name": [{"family": "Smith", "given": ["Jane"]}],
                }
            },
        ],
    }
    fhir_response = create_fhir_get_response(json.dumps(mixed_response))
    resources = fhir_response.get_resources_except_operation_outcomes()
    assert len(resources) == 1
    assert resources[0]["resourceType"] == "Patient"
    assert resources[0]["id"] == "2"
