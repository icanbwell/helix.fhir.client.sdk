import json
from typing import Any

import pytest
from compressedfhir.fhir.fhir_resource import FhirResource
from compressedfhir.fhir.fhir_resource_list import FhirResourceList
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.get.fhir_get_bundle_response import FhirGetBundleResponse
from helix_fhir_client_sdk.responses.get.fhir_get_error_response import FhirGetErrorResponse
from helix_fhir_client_sdk.responses.get.fhir_get_list_by_resource_type_response import (
    FhirGetListByResourceTypeResponse,
)
from helix_fhir_client_sdk.responses.get.fhir_get_list_response import FhirGetListResponse
from helix_fhir_client_sdk.responses.get.fhir_get_response_factory import FhirGetResponseFactory
from helix_fhir_client_sdk.responses.get.fhir_get_single_response import FhirGetSingleResponse

# Synthetic data only (no PHI).  The family name is non-ASCII so the two text modes differ.
PATIENT: dict[str, Any] = {"resourceType": "Patient", "id": "p1", "name": [{"family": "Zoë"}]}
BUNDLE: dict[str, Any] = {"resourceType": "Bundle", "type": "searchset", "entry": [{"resource": PATIENT}]}
OPERATION_OUTCOME: dict[str, Any] = {
    "resourceType": "OperationOutcome",
    "issue": [{"severity": "error", "code": "not-found", "diagnostics": "Zoë"}],
}


def _create(body: Any, *, byte_identical_json: bool, status: int = 200) -> FhirGetResponse:
    return FhirGetResponseFactory.create(
        request_id="request-1",
        url="https://example.com/fhir/Patient",
        response_text=json.dumps(body, ensure_ascii=False),
        error=None,
        access_token=None,
        total_count=1,
        status=status,
        next_url=None,
        extra_context_to_return=None,
        resource_type="Patient",
        id_="p1",
        response_headers=None,
        results_by_url=[],
        storage_mode=CompressedDictStorageMode.default(),
        byte_identical_json=byte_identical_json,
        create_operation_outcome_for_error=False,
    )


@pytest.mark.parametrize(
    "body, status, expected_type",
    [
        (PATIENT, 200, FhirGetSingleResponse),
        ([PATIENT], 200, FhirGetListResponse),
        (BUNDLE, 200, FhirGetBundleResponse),
        (OPERATION_OUTCOME, 404, FhirGetErrorResponse),
    ],
)
def test_response_text_is_compact_utf8_by_default_and_escaped_text_when_byte_identical(
    body: Any, status: int, expected_type: type[FhirGetResponse]
) -> None:
    default_response = _create(body, byte_identical_json=False, status=status)
    exact_response = _create(body, byte_identical_json=True, status=status)

    default_text = default_response.get_response_text()
    exact_text = exact_response.get_response_text()

    assert isinstance(default_response, expected_type)
    assert "Zoë" in default_text
    assert ": " not in default_text.replace("Zoë", "")
    assert "\\u00eb" in exact_text
    assert json.loads(default_text) == json.loads(exact_text)


@pytest.mark.parametrize("byte_identical_json", [False, True])
def test_list_by_resource_type_response_text_follows_the_flag(byte_identical_json: bool) -> None:
    response = FhirGetListByResourceTypeResponse(
        request_id=None,
        url="https://example.com/fhir",
        resources=FhirResourceList(
            [FhirResource(initial_dict=PATIENT, storage_mode=CompressedDictStorageMode.default())]
        ),
        error=None,
        access_token=None,
        total_count=1,
        status=200,
        extra_context_to_return=None,
        resource_type=None,
        id_=None,
        response_headers=None,
        results_by_url=[],
        storage_mode=CompressedDictStorageMode.default(),
        byte_identical_json=byte_identical_json,
    )

    assert ("\\u00eb" in response.get_response_text()) is byte_identical_json
    assert ("Zoë" in response.get_response_text()) is not byte_identical_json


@pytest.mark.parametrize("byte_identical_json", [False, True])
def test_from_response_and_append_keep_the_flag(byte_identical_json: bool) -> None:
    single = _create(PATIENT, byte_identical_json=byte_identical_json)
    listing = _create([PATIENT], byte_identical_json=byte_identical_json)

    bundle = FhirGetBundleResponse.from_response(single)
    appended = listing.append(single)

    assert bundle.byte_identical_json is byte_identical_json
    assert appended.byte_identical_json is byte_identical_json
    assert ("\\u00eb" in bundle.get_response_text()) is byte_identical_json
    assert ("\\u00eb" in appended.get_response_text()) is byte_identical_json


def _all_response_classes() -> list[type[FhirGetResponse]]:
    found: list[type[FhirGetResponse]] = []
    pending: list[type[Any]] = [FhirGetResponse]
    while pending:
        for subclass in pending.pop().__subclasses__():
            if subclass.__module__.startswith("helix_fhir_client_sdk.responses.get."):
                found.append(subclass)
            pending.append(subclass)
    return found


def test_every_response_class_is_covered_by_this_module() -> None:
    covered = {
        FhirGetSingleResponse,
        FhirGetListResponse,
        FhirGetBundleResponse,
        FhirGetErrorResponse,
        FhirGetListByResourceTypeResponse,
    }

    # A new response type must be added to the tests above, or its text builder can silently ignore the flag
    assert {c for c in _all_response_classes() if "test" not in c.__module__} <= covered


def test_clone_keeps_byte_identical_json() -> None:
    client = FhirClient().byte_identical_json()

    assert client.clone()._byte_identical_json is True
    assert FhirClient().clone()._byte_identical_json is False
    assert FhirClient().byte_identical_json().byte_identical_json(False)._byte_identical_json is False
