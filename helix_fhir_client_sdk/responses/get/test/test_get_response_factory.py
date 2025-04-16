import json
from typing import Any

import pytest
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)

from helix_fhir_client_sdk.exceptions.fhir_get_exception import FhirGetException
from helix_fhir_client_sdk.responses.get.fhir_get_bundle_response import (
    FhirGetBundleResponse,
)
from helix_fhir_client_sdk.responses.get.fhir_get_error_response import (
    FhirGetErrorResponse,
)
from helix_fhir_client_sdk.responses.get.fhir_get_list_response import (
    FhirGetListResponse,
)
from helix_fhir_client_sdk.responses.get.fhir_get_response_factory import (
    FhirGetResponseFactory,
)
from helix_fhir_client_sdk.responses.get.fhir_get_single_response import (
    FhirGetSingleResponse,
)


class TestFhirGetResponseFactory:
    @pytest.fixture
    def default_params(self) -> dict[str, Any]:
        """Provide default parameters for creating responses."""
        return {
            "request_id": "test-request",
            "url": "https://example.com",
            "access_token": "test-token",
            "total_count": 1,
            "next_url": None,
            "extra_context_to_return": {},
            "resource_type": "Patient",
            "id_": ["123"],
            "response_headers": None,
            "chunk_number": 1,
            "cache_hits": 0,
            "results_by_url": [],
            "error": None,
            "storage_mode": CompressedDictStorageMode.default(),
            "create_operation_outcome_for_error": False,
        }

    def test_create_error_response(self, default_params: dict[str, Any]) -> None:
        """Test creating an error response."""
        params = default_params.copy()
        params.update(
            {
                "status": 404,
                "response_text": json.dumps({"error": "Not Found"}),
                "error": "Resource not found",
            }
        )

        response = FhirGetResponseFactory.create(**params)

        assert isinstance(response, FhirGetErrorResponse)
        assert response.status == 404
        assert response.error == "Resource not found"

    def test_create_list_response(self, default_params: dict[str, Any]) -> None:
        """Test creating a list response."""
        params = default_params.copy()
        params.update(
            {
                "status": 200,
                "response_text": json.dumps(
                    [
                        {"resourceType": "Patient", "id": "123"},
                        {"resourceType": "Patient", "id": "456"},
                    ]
                ),
            }
        )

        response = FhirGetResponseFactory.create(**params)

        assert isinstance(response, FhirGetListResponse)
        assert response.status == 200

    def test_create_bundle_response(self, default_params: dict[str, Any]) -> None:
        """Test creating a bundle response."""
        params = default_params.copy()
        params.update(
            {
                "status": 200,
                "response_text": json.dumps(
                    {
                        "resourceType": "Bundle",
                        "type": "searchset",
                        "entry": [
                            {"resource": {"resourceType": "Patient", "id": "123"}},
                            {"resource": {"resourceType": "Observation", "id": "456"}},
                        ],
                    }
                ),
            }
        )

        response = FhirGetResponseFactory.create(**params)

        assert isinstance(response, FhirGetBundleResponse)
        assert response.status == 200

    def test_create_single_resource_response(self, default_params: dict[str, Any]) -> None:
        """Test creating a single resource response."""
        params = default_params.copy()
        params.update(
            {
                "status": 200,
                "response_text": json.dumps({"resourceType": "Patient", "id": "123", "name": "John Doe"}),
            }
        )

        response = FhirGetResponseFactory.create(**params)

        assert isinstance(response, FhirGetSingleResponse)
        assert response.status == 200

    def test_create_response_with_none_resources(self, default_params: dict[str, Any]) -> None:
        """Test creating a response with None resources."""
        params = default_params.copy()
        params.update({"status": 200, "response_text": json.dumps(None)})

        with pytest.raises(FhirGetException):  # Adjust the specific exception as needed
            FhirGetResponseFactory.create(**params)

    def test_create_response_with_invalid_json(self, default_params: dict[str, Any]) -> None:
        """Test creating a response with invalid JSON."""
        params = default_params.copy()
        params.update({"status": 200, "response_text": "invalid json"})

        response = FhirGetResponseFactory.create(**params)
        # should return an error response
        assert isinstance(response, FhirGetErrorResponse)

    def test_create_response_with_optional_parameters(self, default_params: dict[str, Any]) -> None:
        """Test creating a response with all optional parameters."""
        params = default_params.copy()
        params.update(
            {
                "status": 200,
                "response_text": json.dumps({"resourceType": "Patient", "id": "123"}),
                "next_url": "https://example.com/next",
                "extra_context_to_return": {"key": "value"},
                "response_headers": ["Content-Type: application/fhir+json"],
                "chunk_number": 2,
                "cache_hits": 1,
            }
        )

        response = FhirGetResponseFactory.create(**params)

        assert isinstance(response, FhirGetSingleResponse)
        assert response.next_url == "https://example.com/next"
        assert response.extra_context_to_return == {"key": "value"}
        assert response.chunk_number == 2
        assert response.cache_hits == 1
