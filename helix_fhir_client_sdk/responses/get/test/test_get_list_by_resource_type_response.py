import json
from typing import List, cast
from unittest.mock import Mock

import pytest

from compressedfhir.fhir.fhir_resource_list import FhirResourceList
from compressedfhir.fhir.fhir_resource_map import FhirResourceMap
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.get.fhir_get_list_by_resource_type_response import (
    FhirGetListByResourceTypeResponse,
)
from compressedfhir.fhir.fhir_resource import FhirResource
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_url_result import (
    RetryableAioHttpUrlResult,
)


class TestFhirGetListByResourceTypeResponse:
    @pytest.fixture
    def sample_resources(self) -> FhirResourceList:
        """Fixture to provide sample resources."""
        return FhirResourceList(
            [
                FhirResource(
                    initial_dict={
                        "resourceType": "Patient",
                        "id": "123",
                        "name": "John Doe",
                    },
                    storage_mode=CompressedDictStorageMode.default(),
                ),
                FhirResource(
                    initial_dict={
                        "resourceType": "Observation",
                        "id": "456",
                        "status": "final",
                    },
                    storage_mode=CompressedDictStorageMode.default(),
                ),
                FhirResource(
                    initial_dict={
                        "resourceType": "Patient",
                        "id": "789",
                        "name": "Jane Smith",
                    },
                    storage_mode=CompressedDictStorageMode.default(),
                ),
            ]
        )

    def test_init(self, sample_resources: FhirResourceList) -> None:
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
            storage_mode=CompressedDictStorageMode.default(),
        )
        assert response.request_id == "test-request"
        assert (
            response._resource_map.get_count_of_resource_types() == 2
        )  # Patient and Observation
        assert len(response._resource_map["Patient"]) == 2
        assert len(response._resource_map["Observation"]) == 1

    def test_parse_resources(self, sample_resources: FhirResourceList) -> None:
        """Test parsing resources from JSON string."""
        resources_json = json.dumps([r.dict() for r in sample_resources])
        parsed_resources = FhirGetListByResourceTypeResponse._parse_resources(
            responses=resources_json
        )
        assert len(parsed_resources) == 3
        assert all("resourceType" in resource for resource in parsed_resources)

    def test_parse_resources_invalid(self) -> None:
        """Test parsing resources with invalid JSON."""
        with pytest.raises(Exception):
            FhirGetListByResourceTypeResponse._parse_resources(responses="invalid json")

    def test_parse_into_resource_map(self, sample_resources: FhirResourceList) -> None:
        """Test parsing resources into a resource map."""
        _, resource_map = FhirGetListByResourceTypeResponse._parse_into_resource_map(
            sample_resources
        )
        assert resource_map.get_count_of_resource_types() == 2
        assert "Patient" in resource_map
        assert "Observation" in resource_map
        assert len(resource_map["Patient"]) == 2
        assert len(resource_map["Observation"]) == 1

    def test_from_response(self, sample_resources: FhirResourceList) -> None:
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
        mock_response.storage_mode = CompressedDictStorageMode.default()

        bundle_response: FhirGetListByResourceTypeResponse = cast(
            FhirGetListByResourceTypeResponse,
            FhirGetListByResourceTypeResponse.from_response(mock_response),
        )
        assert bundle_response.request_id == "test-request"
        assert bundle_response._resource_map.get_count_of_resource_types() == 2

    def test_get_response_text(self, sample_resources: FhirResourceList) -> None:
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
            storage_mode=CompressedDictStorageMode.default(),
        )
        response_text = response.get_response_text()
        assert "Patient" in response_text
        assert "Observation" in response_text
        assert "123" in response_text
        assert "456" in response_text

    def test_append(self, sample_resources: FhirResourceList) -> None:
        """Test appending another response."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        first_response = FhirGetListByResourceTypeResponse(
            request_id="test-request-1",
            url="https://example.com",
            resources=FhirResourceList(list(sample_resources)[:2]),
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
            storage_mode=CompressedDictStorageMode.default(),
        )
        second_response = FhirGetListByResourceTypeResponse(
            request_id="test-request-2",
            url="https://example.com/next",
            resources=FhirResourceList([sample_resources[2]]),
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
            storage_mode=CompressedDictStorageMode.default(),
        )
        first_response._append(second_response)
        assert len(first_response._resource_map["Patient"]) == 2
        assert len(first_response._resource_map["Observation"]) == 1

    async def test_unimplemented_methods(
        self, sample_resources: FhirResourceList
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
            storage_mode=CompressedDictStorageMode.default(),
        )

        # Test methods that raise NotImplementedError
        with pytest.raises(NotImplementedError):
            response.get_bundle_entries()

        with pytest.raises(NotImplementedError):
            async for _ in response.consume_bundle_entry_async():
                pass

    def test_sort_resources(self, sample_resources: FhirResourceList) -> None:
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
            storage_mode=CompressedDictStorageMode.default(),
        )
        sorted_response = response.sort_resources()
        assert isinstance(sorted_response, FhirGetListByResourceTypeResponse)

    async def test_consume_resource_async(
        self, sample_resources: FhirResourceList
    ) -> None:
        """Test the async consume_resource_async method."""
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
            storage_mode=CompressedDictStorageMode.default(),
        )

        # Collect resources from the async generator
        consumed_resources: List[FhirResourceMap] = []
        async for resource_map in response.consume_resource_map_async():
            consumed_resources.append(resource_map)

        # Verify the results
        assert len(consumed_resources) == 1
        assert isinstance(consumed_resources[0], FhirResourceMap)

        # Check the structure of the resource map
        resource_dict = consumed_resources[0].dict()
        assert "Patient" in resource_dict
        assert "Observation" in resource_dict
        assert len(resource_dict["Patient"]) == 2
        assert len(resource_dict["Observation"]) == 1

    def test_consume_resource(self, sample_resources: FhirResourceList) -> None:
        """Test the synchronous consume_resource method."""
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
            storage_mode=CompressedDictStorageMode.default(),
        )

        # Collect resources from the generator
        consumed_resources: List[FhirResourceMap] = []
        for resource_map in response.consume_resource_map():
            consumed_resources.append(resource_map)

        # Verify the results
        assert len(consumed_resources) == 1
        assert isinstance(consumed_resources[0], FhirResourceMap)

        # Check the structure of the resource map
        resource_dict = consumed_resources[0].dict()
        assert "Patient" in resource_dict
        assert "Observation" in resource_dict
        assert len(resource_dict["Patient"]) == 2
        assert len(resource_dict["Observation"]) == 1
