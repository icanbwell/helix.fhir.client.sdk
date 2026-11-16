"""FhirGetBundleResponse.from_response() builds the bundle response from the other response's entries
without serializing them into a bundle and parsing it back. The result must be the same as before.
All data is synthetic."""

import json
from collections.abc import Callable
from typing import Any

import pytest
from compressedfhir.fhir.fhir_bundle import FhirBundle
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)

from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.get.fhir_get_bundle_response import (
    FhirGetBundleResponse,
)
from helix_fhir_client_sdk.responses.get.fhir_get_response_factory import (
    FhirGetResponseFactory,
)

PATIENT: dict[str, Any] = {"resourceType": "Patient", "id": "p1", "active": True}
OBSERVATION: dict[str, Any] = {"resourceType": "Observation", "id": "o1", "status": "final"}
OPERATION_OUTCOME: dict[str, Any] = {
    "resourceType": "OperationOutcome",
    "issue": [{"severity": "error", "code": "not-found", "diagnostics": "synthetic"}],
}
HEADERS: list[str] = ["Last-Modified: Tue, 10 Nov 2020 08:00:00 GMT", 'ETag: W/"3"']


def _other(
    *, body: Any, status: int = 200, error: str | None = None, headers: list[str] | None = None
) -> Callable[[CompressedDictStorageMode], FhirGetResponse]:
    def create(storage_mode: CompressedDictStorageMode) -> FhirGetResponse:
        return FhirGetResponseFactory.create(
            request_id="request-1",
            url="https://example.com/fhir/Patient/p1",
            response_text=json.dumps(body) if body is not None else "",
            error=error,
            access_token=None,
            total_count=1,
            status=status,
            next_url=None,
            extra_context_to_return={"slug": "synthetic"},
            resource_type="Patient",
            id_="p1",
            response_headers=headers,
            results_by_url=[],
            storage_mode=storage_mode,
            create_operation_outcome_for_error=True,
        )

    return create


def _previous_from_response(other_response: FhirGetResponse) -> FhirGetBundleResponse:
    """The previous implementation: serialize the entries into a bundle, parse it, then replace the entries."""
    bundle = FhirBundle(entry=other_response.get_bundle_entries(), type_="collection")
    response = FhirGetBundleResponse(
        request_id=other_response.request_id,
        url=other_response.url,
        response_text=bundle.json(),
        error=other_response.error,
        access_token=other_response.access_token,
        total_count=other_response.total_count,
        status=other_response.status,
        next_url=other_response.next_url,
        extra_context_to_return=other_response.extra_context_to_return,
        resource_type=other_response.resource_type,
        id_=other_response.id_,
        response_headers=other_response.response_headers,
        chunk_number=other_response.chunk_number,
        cache_hits=other_response.cache_hits,
        results_by_url=other_response.results_by_url,
        storage_mode=other_response.storage_mode,
    )
    response._bundle_entries = other_response.get_bundle_entries()
    return response


def _observable_output(response: FhirGetResponse) -> dict[str, Any]:
    return {
        "class": type(response).__name__,
        "to_dict": response.to_dict(),
        "response_text": response.get_response_text(),
        "bundle_entries": [entry.dict() for entry in response.get_bundle_entries()],
        "error": response.error,
        "status": response.status,
        "last_modified": response.lastModified,
        "etag": response.etag,
    }


@pytest.mark.parametrize("storage_mode", [CompressedDictStorageMode.raw(), CompressedDictStorageMode.compressed()])
@pytest.mark.parametrize(
    "make_other",
    [
        pytest.param(_other(body=PATIENT), id="single"),
        pytest.param(_other(body=PATIENT, headers=HEADERS), id="single_with_headers"),
        pytest.param(_other(body=[PATIENT, OBSERVATION], headers=HEADERS), id="list"),
        pytest.param(_other(body=[]), id="empty_list"),
        pytest.param(_other(body=OPERATION_OUTCOME, status=404), id="not_found"),
        pytest.param(_other(body=None, status=500, error="synthetic error"), id="error_without_body"),
        pytest.param(_other(body=PATIENT, error="synthetic error"), id="error_with_body"),
    ],
)
def test_from_response_matches_previous_implementation(
    make_other: Callable[[CompressedDictStorageMode], FhirGetResponse], storage_mode: CompressedDictStorageMode
) -> None:
    # Arrange
    expected = _previous_from_response(make_other(storage_mode))
    other = make_other(storage_mode)
    other_entries_before = [entry.dict() for entry in other.get_bundle_entries()]

    # Act
    result = FhirGetBundleResponse.from_response(other_response=other)

    # Assert
    assert _observable_output(result) == _observable_output(expected)
    assert [entry.dict() for entry in other.get_bundle_entries()] == other_entries_before


def test_from_response_returns_a_bundle_response_unchanged() -> None:
    bundle_response = _other(body={"resourceType": "Bundle", "type": "searchset", "entry": [{"resource": PATIENT}]})(
        CompressedDictStorageMode.raw()
    )
    assert isinstance(bundle_response, FhirGetBundleResponse)

    assert FhirGetBundleResponse.from_response(other_response=bundle_response) is bundle_response
