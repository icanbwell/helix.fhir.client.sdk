import json
from typing import Any
from unittest.mock import Mock

import pytest
from compressedfhir.fhir.fhir_bundle_entry import (
    FhirBundleEntry,
)
from compressedfhir.fhir.fhir_resource_list import FhirResourceList
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)

from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.get.fhir_get_error_response import (
    FhirGetErrorResponse,
)


class TestFhirGetErrorResponse:
    @pytest.fixture
    def sample_error_response(self) -> dict[str, Any]:
        """Fixture to provide a sample error response."""
        return {
            "resourceType": "OperationOutcome",
            "issue": [
                {
                    "severity": "error",
                    "code": "processing",
                    "diagnostics": "Sample error message",
                }
            ],
        }

    @pytest.fixture
    def base_response_params(self) -> dict[str, Any]:
        """Fixture to provide base parameters for creating a response."""
        return {
            "request_id": "test-request",
            "url": "https://example.com",
            "access_token": "test-token",
            "total_count": 0,
            "status": 400,
            "next_url": None,
            "extra_context_to_return": {},
            "resource_type": "Patient",
            "id_": ["123"],
            "response_headers": None,
            "chunk_number": 1,
            "cache_hits": 0,
            "results_by_url": [],
            "storage_mode": CompressedDictStorageMode.default(),
            "create_operation_outcome_for_error": True,
        }

    def test_init(
        self,
        base_response_params: dict[str, Any],
        sample_error_response: dict[str, Any],
    ) -> None:
        """Test initialization of FhirGetErrorResponse."""

        response = FhirGetErrorResponse(
            **base_response_params,
            response_text=json.dumps(sample_error_response),
            error="Sample error",
        )

        assert response.request_id == "test-request"
        assert response.status == 400
        assert response._resource is not None
        assert response._resource["resourceType"] == "OperationOutcome"

    def test_get_resources(
        self,
        base_response_params: dict[str, Any],
        sample_error_response: dict[str, Any],
    ) -> None:
        """Test getting resources from the error response."""

        response = FhirGetErrorResponse(
            **base_response_params,
            response_text=json.dumps(sample_error_response),
            error="Sample error",
        )

        resources = response.get_resources()
        assert isinstance(resources, FhirResourceList)
        assert len(resources) == 1
        assert resources[0]["resourceType"] == "OperationOutcome"

    def test_get_bundle_entries(
        self,
        base_response_params: dict[str, Any],
        sample_error_response: dict[str, Any],
    ) -> None:
        """Test getting bundle entries from the error response."""

        response = FhirGetErrorResponse(
            **base_response_params,
            response_text=json.dumps(sample_error_response),
            error="Sample error",
        )

        entries = response.get_bundle_entries()
        assert len(entries) == 1
        assert isinstance(entries[0], FhirBundleEntry)
        assert entries[0].resource is not None
        assert entries[0].resource["resourceType"] == "OperationOutcome"

    def test_get_response_text(
        self,
        base_response_params: dict[str, Any],
        sample_error_response: dict[str, Any],
    ) -> None:
        """Test getting the response text."""

        response = FhirGetErrorResponse(
            **base_response_params,
            response_text=json.dumps(sample_error_response),
            error="Sample error",
        )

        response_text = response.get_response_text()
        assert "OperationOutcome" in response_text

    @pytest.mark.asyncio
    async def test_consume_resource_async(
        self,
        base_response_params: dict[str, Any],
        sample_error_response: dict[str, Any],
    ) -> None:
        """Test async resources generator."""

        response = FhirGetErrorResponse(
            **base_response_params,
            response_text=json.dumps(sample_error_response),
            error="Sample error",
        )

        assert response.get_resource_count() == 1

        resources = []
        async for resource in response.consume_resource_async():
            resources.append(resource)

        assert len(resources) == 1
        assert resources[0]["resourceType"] == "OperationOutcome"
        assert response.get_resource_count() == 0

    def test_consume_resource(
        self,
        base_response_params: dict[str, Any],
        sample_error_response: dict[str, Any],
    ) -> None:
        """Test async resources generator."""

        response = FhirGetErrorResponse(
            **base_response_params,
            response_text=json.dumps(sample_error_response),
            error="Sample error",
        )

        assert response.get_resource_count() == 1

        resources = []
        for resource in response.consume_resource():
            resources.append(resource)

        assert len(resources) == 1
        assert resources[0]["resourceType"] == "OperationOutcome"
        assert response.get_resource_count() == 0

    @pytest.mark.asyncio
    async def test_consume_bundle_entry_async(
        self,
        base_response_params: dict[str, Any],
        sample_error_response: dict[str, Any],
    ) -> None:
        """Test async bundle entries generator."""

        response = FhirGetErrorResponse(
            **base_response_params,
            response_text=json.dumps(sample_error_response),
            error="Sample error",
        )

        entries = []
        async for entry in response.consume_bundle_entry_async():
            entries.append(entry)

        assert len(entries) == 1
        assert isinstance(entries[0], FhirBundleEntry)
        assert entries[0].resource is not None
        assert entries[0].resource["resourceType"] == "OperationOutcome"
        assert response.get_resource_count() == 0

    def test_consume_bundle_entry(
        self,
        base_response_params: dict[str, Any],
        sample_error_response: dict[str, Any],
    ) -> None:
        """Test async bundle entries generator."""

        response = FhirGetErrorResponse(
            **base_response_params,
            response_text=json.dumps(sample_error_response),
            error="Sample error",
        )

        entries = []
        for entry in response.consume_bundle_entry():
            entries.append(entry)

        assert len(entries) == 1
        assert isinstance(entries[0], FhirBundleEntry)
        assert entries[0].resource is not None
        assert entries[0].resource["resourceType"] == "OperationOutcome"
        assert response.get_resource_count() == 0

    def test_from_response_raises_not_implemented(
        self,
        base_response_params: dict[str, Any],
        sample_error_response: dict[str, Any],
    ) -> None:
        """Test that from_response method raises NotImplementedError."""

        mock_response = Mock(spec=FhirGetResponse)
        with pytest.raises(
            NotImplementedError,
            match="FhirSingleGetResponse does not support from_response()",
        ):
            FhirGetErrorResponse.from_response(mock_response)
