import json
from typing import Dict, Any, List
from unittest.mock import Mock

import pytest

from helix_fhir_client_sdk.fhir.bundle_entry import (
    BundleEntry,
)
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.get_responses.fhir_get_error_response import (
    FhirGetErrorResponse,
)
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)


class TestFhirGetErrorResponse:
    @pytest.fixture
    def sample_error_response(self) -> Dict[str, Any]:
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
    def base_response_params(self) -> Dict[str, Any]:
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
        }

    def test_init(
        self,
        base_response_params: Dict[str, Any],
        sample_error_response: Dict[str, Any],
    ) -> None:
        """Test initialization of FhirGetErrorResponse."""

        response = FhirGetErrorResponse(
            **base_response_params,
            response_text=json.dumps(sample_error_response),
            error="Sample error",
            storage_mode=CompressedDictStorageMode(),
        )

        assert response.request_id == "test-request"
        assert response.status == 400
        assert response._resource is not None
        assert response._resource["resourceType"] == "OperationOutcome"

    def test_get_resources(
        self,
        base_response_params: Dict[str, Any],
        sample_error_response: Dict[str, Any],
    ) -> None:
        """Test getting resources from the error response."""

        response = FhirGetErrorResponse(
            **base_response_params,
            response_text=json.dumps(sample_error_response),
            error="Sample error",
            storage_mode=CompressedDictStorageMode(),
        )

        resources = response.get_resources()
        assert len(resources) == 1
        assert resources[0]["resourceType"] == "OperationOutcome"

    def test_get_bundle_entries(
        self,
        base_response_params: Dict[str, Any],
        sample_error_response: Dict[str, Any],
    ) -> None:
        """Test getting bundle entries from the error response."""

        response = FhirGetErrorResponse(
            **base_response_params,
            response_text=json.dumps(sample_error_response),
            error="Sample error",
            storage_mode=CompressedDictStorageMode(),
        )

        entries = response.get_bundle_entries()
        assert len(entries) == 1
        assert isinstance(entries[0], BundleEntry)
        assert entries[0].resource is not None
        assert entries[0].resource["resourceType"] == "OperationOutcome"

    def test_append_raises_not_implemented(
        self,
        base_response_params: Dict[str, Any],
        sample_error_response: Dict[str, Any],
    ) -> None:
        """Test that append method raises NotImplementedError."""

        response = FhirGetErrorResponse(
            **base_response_params,
            response_text=json.dumps(sample_error_response),
            error="Sample error",
            storage_mode=CompressedDictStorageMode(),
        )

        mock_other_response = Mock(spec=FhirGetResponse)
        with pytest.raises(
            NotImplementedError,
            match="FhirGetErrorResponse does not support appending other responses.",
        ):
            response.append(mock_other_response)

    def test_extend_raises_not_implemented(
        self,
        base_response_params: Dict[str, Any],
        sample_error_response: Dict[str, Any],
    ) -> None:
        """Test that extend method raises NotImplementedError."""

        response = FhirGetErrorResponse(
            **base_response_params,
            response_text=json.dumps(sample_error_response),
            error="Sample error",
            storage_mode=CompressedDictStorageMode(),
        )

        mock_other_responses: List[FhirGetResponse] = [Mock(spec=FhirGetResponse)]
        with pytest.raises(
            NotImplementedError,
            match="FhirGetErrorResponse does not support extending with other responses.",
        ):
            response.extend(mock_other_responses)

    def test_get_response_text(
        self,
        base_response_params: Dict[str, Any],
        sample_error_response: Dict[str, Any],
    ) -> None:
        """Test getting the response text."""

        response = FhirGetErrorResponse(
            **base_response_params,
            response_text=json.dumps(sample_error_response),
            error="Sample error",
            storage_mode=CompressedDictStorageMode(),
        )

        response_text = response.get_response_text()
        assert "OperationOutcome" in response_text

    @pytest.mark.asyncio
    async def test_get_resources_generator(
        self,
        base_response_params: Dict[str, Any],
        sample_error_response: Dict[str, Any],
    ) -> None:
        """Test async resources generator."""

        response = FhirGetErrorResponse(
            **base_response_params,
            response_text=json.dumps(sample_error_response),
            error="Sample error",
            storage_mode=CompressedDictStorageMode(),
        )

        resources = []
        async for resource in response.get_resources_generator():
            resources.append(resource)

        assert len(resources) == 1
        assert resources[0]["resourceType"] == "OperationOutcome"

    @pytest.mark.asyncio
    async def test_get_bundle_entries_generator(
        self,
        base_response_params: Dict[str, Any],
        sample_error_response: Dict[str, Any],
    ) -> None:
        """Test async bundle entries generator."""

        response = FhirGetErrorResponse(
            **base_response_params,
            response_text=json.dumps(sample_error_response),
            error="Sample error",
            storage_mode=CompressedDictStorageMode(),
        )

        entries = []
        async for entry in response.get_bundle_entries_generator():
            entries.append(entry)

        assert len(entries) == 1
        assert isinstance(entries[0], BundleEntry)
        assert entries[0].resource is not None
        assert entries[0].resource["resourceType"] == "OperationOutcome"

    def test_from_response_raises_not_implemented(
        self,
        base_response_params: Dict[str, Any],
        sample_error_response: Dict[str, Any],
    ) -> None:
        """Test that from_response method raises NotImplementedError."""

        mock_response = Mock(spec=FhirGetResponse)
        with pytest.raises(
            NotImplementedError,
            match="FhirSingleGetResponse does not support from_response()",
        ):
            FhirGetErrorResponse.from_response(mock_response)
