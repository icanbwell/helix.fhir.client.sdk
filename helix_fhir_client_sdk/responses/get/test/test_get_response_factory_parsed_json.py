import json
from typing import Any

import pytest
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)

from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.get.fhir_get_response_factory import (
    FhirGetResponseFactory,
)

# Synthetic resources only
PATIENT: dict[str, Any] = {"resourceType": "Patient", "id": "p1", "active": True}
OBSERVATION: dict[str, Any] = {
    "resourceType": "Observation",
    "id": "o1",
    "status": "final",
    "valueQuantity": {"value": 1.5, "unit": "mg"},
    "subject": {"reference": "Patient/p1"},
}
BUNDLE: dict[str, Any] = {
    "resourceType": "Bundle",
    "id": "b1",
    "type": "searchset",
    "timestamp": "2020-01-01T00:00:00Z",
    "total": 2,
    "entry": [
        {"fullUrl": "https://example.com/Patient/p1", "resource": PATIENT},
        {
            "resource": OBSERVATION,
            "request": {"method": "GET", "url": "Observation/o1"},
            "response": {"status": "200", "etag": 'W/"1"'},
        },
    ],
}
EMPTY_BUNDLE: dict[str, Any] = {"resourceType": "Bundle", "type": "searchset", "total": 0}
ENTRY_WITHOUT_RESOURCE_TYPE: dict[str, Any] = {"entry": [{"resource": PATIENT}]}

STORAGE_MODES = [CompressedDictStorageMode.raw(), CompressedDictStorageMode.compressed()]


def _params(*, status: int, error: str | None, storage_mode: CompressedDictStorageMode) -> dict[str, Any]:
    return {
        "request_id": "request-1",
        "url": "https://example.com/fhir/Patient",
        "error": error,
        "access_token": None,
        "total_count": 2,
        "status": status,
        "next_url": None,
        "extra_context_to_return": {"slug": "synthetic"},
        "resource_type": "Patient",
        "id_": None,
        "response_headers": ['ETag: W/"5"', "Content-Type: application/fhir+json"],
        "results_by_url": [],
        "storage_mode": storage_mode,
        "create_operation_outcome_for_error": False,
    }


def _observable_output(response: FhirGetResponse) -> dict[str, Any]:
    """Everything a caller can see from the response"""
    return {
        "class": type(response).__name__,
        "to_dict": response.to_dict(),
        "response_text": response.get_response_text(),
        "bundle_entries": [entry.dict() for entry in response.get_bundle_entries()],
        "resource_count": response.get_resource_count(),
    }


@pytest.mark.parametrize("storage_mode", STORAGE_MODES, ids=["raw", "compressed"])
@pytest.mark.parametrize(
    "parsed_json, status, error",
    [
        (PATIENT, 200, None),
        ([PATIENT, OBSERVATION], 200, None),
        ([], 200, None),
        (BUNDLE, 200, None),
        (EMPTY_BUNDLE, 200, None),
        (ENTRY_WITHOUT_RESOURCE_TYPE, 200, None),
        ({}, 200, None),
        (PATIENT, 404, None),
        (PATIENT, 200, "synthetic error"),
    ],
    ids=[
        "single",
        "list",
        "empty_list",
        "bundle",
        "empty_bundle",
        "entry_without_resource_type",
        "empty_object",
        "not_found",
        "error",
    ],
)
def test_create_from_parsed_json_matches_create_from_text(
    parsed_json: dict[str, Any] | list[dict[str, Any]],
    status: int,
    error: str | None,
    storage_mode: CompressedDictStorageMode,
) -> None:
    # Arrange
    params = _params(status=status, error=error, storage_mode=storage_mode)

    # Act
    from_text = FhirGetResponseFactory.create(response_text=json.dumps(parsed_json), **params)
    from_parsed = FhirGetResponseFactory.create_from_parsed_json(
        parsed_json=json.loads(json.dumps(parsed_json)), **params
    )

    # Assert
    assert _observable_output(from_parsed) == _observable_output(from_text)


@pytest.mark.parametrize(
    "response_text",
    [
        json.dumps(BUNDLE),
        json.dumps(BUNDLE, indent=2),
        json.dumps([PATIENT, OBSERVATION]),
        json.dumps(PATIENT),
        "",
    ],
    ids=["bundle", "bundle_indented", "list", "single", "empty"],
)
def test_create_parses_successful_response_text_once(response_text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    real_loads = json.loads
    calls: list[str] = []

    def counting_loads(s: Any, *args: Any, **kwargs: Any) -> Any:
        calls.append(s)
        return real_loads(s, *args, **kwargs)

    monkeypatch.setattr(json, "loads", counting_loads)

    # Act
    response = FhirGetResponseFactory.create(
        response_text=response_text,
        **_params(status=200, error=None, storage_mode=CompressedDictStorageMode.raw()),
    )

    # Assert
    assert [c for c in calls if c == response_text] == ([response_text] if response_text else [])
    assert response is not None
