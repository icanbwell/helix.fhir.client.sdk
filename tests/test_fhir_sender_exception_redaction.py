"""DCON-6540: FhirSenderException redacts credentials and identifier variables when it is created."""

import json
from typing import Any

import pytest

from helix_fhir_client_sdk.exceptions.fhir_sender_exception import FhirSenderException
from helix_fhir_client_sdk.filters.identifier_filter import IdentifierFilter

ACCESS_TOKEN = "synthetic-access-token-0001"
REDACTED = "[REDACTED]"


@pytest.mark.parametrize(
    "header_name",
    [
        "Authorization",
        "authorization",
        "Proxy-Authorization",
        "Cookie",
        # vendor credentials that patient access sends as custom FHIR API headers
        "X-Api-Key",
        "Ocp-Apim-Subscription-Key",
        "X-Auth-Token",
    ],
)
def test_credential_header_is_redacted_when_the_exception_is_created(header_name: str) -> None:
    # Arrange
    headers = {
        "Accept": "application/fhir+json",
        "Origin-Service": "test-service",
        header_name: f"Bearer {ACCESS_TOKEN}",
    }

    # Act
    exception = FhirSenderException(message="", headers=headers)

    # Assert
    assert exception.headers == {
        "Accept": "application/fhir+json",
        "Origin-Service": "test-service",
        header_name: REDACTED,
    }
    assert ACCESS_TOKEN not in json.dumps(exception.to_dict(), default=str)


@pytest.mark.parametrize("headers", [None, {}])
def test_no_headers_gives_empty_headers(headers: dict[str, str] | None) -> None:
    # Act
    exception = FhirSenderException(message="", headers=headers)

    # Assert
    assert exception.headers == {}


def test_exception_headers_are_a_redacted_copy_of_the_request_headers() -> None:
    # Arrange
    request_headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

    # Act
    exception = FhirSenderException(message="", headers=request_headers)
    # the request queue writes the bearer token of the next request into the same dict
    request_headers["Authorization"] = "Bearer synthetic-access-token-0002"

    # Assert
    assert exception.headers == {"Authorization": REDACTED}


def test_creating_the_exception_does_not_change_the_callers_headers_or_variables() -> None:
    # Arrange: the variables hold references to the live attributes of the FHIR client
    request_headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    client_additional_headers = {"X-Api-Key": ACCESS_TOKEN}
    ids = ["patient-test-001"]
    variables: dict[str, Any] = {"_id": ids, "_additional_request_headers": client_additional_headers}

    # Act
    FhirSenderException(message="", headers=request_headers, variables=variables)

    # Assert
    assert request_headers == {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    assert variables == {"_id": ["patient-test-001"], "_additional_request_headers": {"X-Api-Key": ACCESS_TOKEN}}


@pytest.mark.parametrize(
    "variables, expected_variables",
    [
        pytest.param({"_id": "patient-test-001"}, {"_id": REDACTED}, id="id"),
        pytest.param({"_id": ["patient-test-001", "patient-test-002"]}, {"_id": REDACTED}, id="id-list"),
        pytest.param({"_obj_id": "patient-test-001"}, {"_obj_id": REDACTED}, id="obj-id"),
        pytest.param(
            {"_additional_parameters": ["patient=patient-test-001"]},
            {"_additional_parameters": REDACTED},
            id="additional-parameters",
        ),
        pytest.param(
            {"_filters": [IdentifierFilter(system="http://example.test/mrn", value="mrn-test-001")]},
            {"_filters": REDACTED},
            id="filters",
        ),
        pytest.param(
            {"_additional_request_headers": {"Authorization": f"Bearer {ACCESS_TOKEN}", "Origin-Service": "test"}},
            {"_additional_request_headers": {"Authorization": REDACTED, "Origin-Service": "test"}},
            id="additional-request-headers",
        ),
        pytest.param(
            {"_id": None, "_obj_id": "", "_filters": [], "_additional_parameters": None},
            {"_id": None, "_obj_id": "", "_filters": [], "_additional_parameters": None},
            id="empty-identifier-variables",
        ),
        pytest.param(
            {"_resource": "Patient", "_url": "http://fhir.example.test/4_0_0", "_retry_count": 2},
            {"_resource": "Patient", "_url": "http://fhir.example.test/4_0_0", "_retry_count": 2},
            id="other-variables",
        ),
        pytest.param(None, {}, id="no-variables"),
    ],
)
def test_identifier_variables_are_redacted_when_the_exception_is_created(
    variables: dict[str, Any] | None, expected_variables: dict[str, Any]
) -> None:
    # Act
    exception = FhirSenderException(message="", variables=variables)

    # Assert
    assert exception.variables == expected_variables
    assert exception.to_dict()["variables"] == expected_variables
