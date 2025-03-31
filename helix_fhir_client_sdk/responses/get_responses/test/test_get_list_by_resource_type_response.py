import json
from typing import List, cast
from unittest.mock import Mock

import pytest

from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.get_responses.fhir_get_list_by_resource_type_response import (
    FhirGetListByResourceTypeResponse,
)
from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_url_result import (
    RetryableAioHttpUrlResult,
)


class TestFhirGetListByResourceTypeResponse:
    @pytest.fixture
    def sample_resources(self) -> List[FhirResource]:
        """Fixture to provide sample resources."""
        return [
            FhirResource(
                initial_dict={
                    "resourceType": "Patient",
                    "id": "123",
                    "name": "John Doe",
                },
                storage_mode=CompressedDictStorageMode(),
            ),
            FhirResource(
                initial_dict={
                    "resourceType": "Observation",
                    "id": "456",
                    "status": "final",
                },
                storage_mode=CompressedDictStorageMode(),
            ),
            FhirResource(
                initial_dict={
                    "resourceType": "Patient",
                    "id": "789",
                    "name": "Jane Smith",
                },
                storage_mode=CompressedDictStorageMode(),
            ),
        ]

    def test_init(self, sample_resources: List[FhirResource]) -> None:
        """Test initialization of FhirGetListByResourceTypeResponse."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetListByResourceTypeResponse(
            request_id="test-request",
            url="https://example.com",
            resources=sample_resources,
            error=None,
            access_token="test-token",
            total_count=3,
            status=200,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["123", "789"],
            response_headers=None,
            chunk_number=1,
            cache_hits=0,
            results_by_url=results_by_url,
            storage_mode=CompressedDictStorageMode(),
        )
        assert response.request_id == "test-request"
        assert len(response._resource_map) == 2  # Patient and Observation
        assert len(response._resource_map["Patient"]) == 2
        assert len(response._resource_map["Observation"]) == 1

    def test_parse_resources(self, sample_resources: List[FhirResource]) -> None:
        """Test parsing resources from JSON string."""
        resources_json = json.dumps([r.to_dict() for r in sample_resources])
        parsed_resources = FhirGetListByResourceTypeResponse._parse_resources(
            responses=resources_json
        )
        assert len(parsed_resources) == 3
        assert all("resourceType" in resource for resource in parsed_resources)

    def test_parse_resources_invalid(self) -> None:
        """Test parsing resources with invalid JSON."""
        with pytest.raises(Exception):
            FhirGetListByResourceTypeResponse._parse_resources(responses="invalid json")

    def test_parse_into_resource_map(
        self, sample_resources: List[FhirResource]
    ) -> None:
        """Test parsing resources into a resource map."""
        _, resource_map = FhirGetListByResourceTypeResponse._parse_into_resource_map(
            sample_resources
        )
        assert len(resource_map) == 2
        assert "Patient" in resource_map
        assert "Observation" in resource_map
        assert len(resource_map["Patient"]) == 2
        assert len(resource_map["Observation"]) == 1

    def test_from_response(self, sample_resources: List[FhirResource]) -> None:
        """Test creating a FhirGetListByResourceTypeResponse from another response."""
        mock_response = Mock(spec=FhirGetResponse)
        mock_response.request_id = "test-request"
        mock_response.url = "https://example.com"
        mock_response.error = None
        mock_response.access_token = "test-token"
        mock_response.total_count = 3
        mock_response.status = 200
        mock_response.results_by_url = []
        mock_response.next_url = None
        mock_response.extra_context_to_return = {}
        mock_response.resource_type = "Patient"
        mock_response.id_ = ["123", "789"]
        mock_response.response_headers = None
        mock_response.chunk_number = 1
        mock_response.cache_hits = 0
        mock_response.get_resources.return_value = sample_resources
        mock_response.storage_mode = CompressedDictStorageMode()

        bundle_response: FhirGetListByResourceTypeResponse = cast(
            FhirGetListByResourceTypeResponse,
            FhirGetListByResourceTypeResponse.from_response(mock_response),
        )
        assert bundle_response.request_id == "test-request"
        assert len(bundle_response._resource_map) == 2

    def test_get_response_text(self, sample_resources: List[FhirResource]) -> None:
        """Test getting the response text as JSON."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetListByResourceTypeResponse(
            request_id="test-request",
            url="https://example.com",
            resources=sample_resources,
            error=None,
            access_token="test-token",
            total_count=3,
            status=200,
            results_by_url=results_by_url,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["123", "789"],
            response_headers=None,
            storage_mode=CompressedDictStorageMode(),
        )
        response_text = response.get_response_text()
        assert "Patient" in response_text
        assert "Observation" in response_text
        assert "123" in response_text
        assert "456" in response_text

    def test_append(self, sample_resources: List[FhirResource]) -> None:
        """Test appending another response."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        first_response = FhirGetListByResourceTypeResponse(
            request_id="test-request-1",
            url="https://example.com",
            resources=sample_resources[:2],
            error=None,
            access_token="test-token",
            total_count=2,
            status=200,
            results_by_url=results_by_url,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["123"],
            response_headers=None,
            storage_mode=CompressedDictStorageMode(),
        )
        second_response = FhirGetListByResourceTypeResponse(
            request_id="test-request-2",
            url="https://example.com/next",
            resources=[sample_resources[2]],
            error=None,
            access_token="test-token",
            total_count=1,
            status=200,
            results_by_url=results_by_url,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["789"],
            response_headers=None,
            storage_mode=CompressedDictStorageMode(),
        )
        first_response._append(second_response)
        assert len(first_response._resource_map["Patient"]) == 2
        assert len(first_response._resource_map["Observation"]) == 1

    async def test_unimplemented_methods(
        self, sample_resources: List[FhirResource]
    ) -> None:
        """Test methods that raise NotImplementedError."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetListByResourceTypeResponse(
            request_id="test-request",
            url="https://example.com",
            resources=sample_resources,
            error=None,
            access_token="test-token",
            total_count=3,
            status=200,
            results_by_url=results_by_url,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["123", "789"],
            response_headers=None,
            storage_mode=CompressedDictStorageMode(),
        )

        # Test methods that raise NotImplementedError
        with pytest.raises(NotImplementedError):
            response.get_bundle_entries()

        with pytest.raises(NotImplementedError):
            response.remove_duplicates()

        with pytest.raises(NotImplementedError):
            async for _ in response.get_resources_generator():
                pass

        with pytest.raises(NotImplementedError):
            async for _ in response.get_bundle_entries_generator():
                pass

    def test_sort_resources(self, sample_resources: List[FhirResource]) -> None:
        """Test sort_resources method."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetListByResourceTypeResponse(
            request_id="test-request",
            url="https://example.com",
            resources=sample_resources,
            error=None,
            access_token="test-token",
            total_count=3,
            status=200,
            results_by_url=results_by_url,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["123", "789"],
            response_headers=None,
            storage_mode=CompressedDictStorageMode(),
        )
        sorted_response = response.sort_resources()
        assert isinstance(sorted_response, FhirGetListByResourceTypeResponse)
