import json
from typing import Dict, Any, List
from unittest.mock import Mock

import pytest

from compressedfhir.fhir.fhir_bundle_entry import (
    FhirBundleEntry,
)
from compressedfhir.fhir.fhir_resource import FhirResource
from compressedfhir.fhir.fhir_resource_list import FhirResourceList
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.get.fhir_get_list_response import (
    FhirGetListResponse,
)
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_url_result import (
    RetryableAioHttpUrlResult,
)


class TestFhirGetListResponse:
    @pytest.fixture
    def sample_resources(self) -> List[Dict[str, Any]]:
        """Fixture to provide sample resources."""
        return [
            {"resourceType": "Patient", "id": "123", "name": "John Doe"},
            {"resourceType": "Observation", "id": "456", "status": "final"},
        ]

    def test_init(self, sample_resources: List[Dict[str, Any]]) -> None:
        """Test initialization of FhirGetListResponse."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetListResponse(
            request_id="test-request",
            url="https://example.com",
            response_text=json.dumps(sample_resources),
            error=None,
            access_token="test-token",
            total_count=2,
            status=200,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["123"],
            response_headers=None,
            chunk_number=1,
            cache_hits=0,
            results_by_url=results_by_url,
            storage_mode=CompressedDictStorageMode.default(),
        )
        assert response.request_id == "test-request"
        resources = response.get_resources()
        assert isinstance(resources, FhirResourceList)
        assert len(resources) == 2
        resource = resources[0]
        with resource.transaction():
            assert resource["resourceType"] == "Patient"

    def test_append(self, sample_resources: List[Dict[str, Any]]) -> None:
        """Test appending another response."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        first_response = FhirGetListResponse(
            request_id="test-request-1",
            url="https://example.com",
            response_text=json.dumps(sample_resources[:1]),
            error=None,
            access_token="test-token",
            total_count=1,
            status=200,
            results_by_url=results_by_url,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["123"],
            response_headers=None,
            storage_mode=CompressedDictStorageMode.default(),
        )
        second_response = FhirGetListResponse(
            request_id="test-request-2",
            url="https://example.com/next",
            response_text=json.dumps(sample_resources[1:]),
            error=None,
            access_token="test-token",
            total_count=1,
            status=200,
            results_by_url=results_by_url,
            next_url=None,
            extra_context_to_return={},
            resource_type="Observation",
            id_=["456"],
            response_headers=None,
            storage_mode=CompressedDictStorageMode.default(),
        )
        first_response.append(second_response)
        resources = first_response.get_resources()
        assert isinstance(resources, FhirResourceList)
        assert len(resources) == 2

    def test_get_resources(self, sample_resources: List[Dict[str, Any]]) -> None:
        """Test getting resources from the response."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetListResponse(
            request_id="test-request",
            url="https://example.com",
            response_text=json.dumps(sample_resources),
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
        resources = response.get_resources()
        assert isinstance(resources, FhirResourceList)
        assert len(resources) == 2
        assert isinstance(resources, FhirResourceList)
        assert resources[0]["resourceType"] == "Patient"
        assert resources[1]["resourceType"] == "Observation"

    def test_remove_duplicates(self, sample_resources: List[Dict[str, Any]]) -> None:
        """Test removing duplicate resources."""
        # Add a duplicate entry to the sample resources
        sample_resources.append(sample_resources[0])
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetListResponse(
            request_id="test-request",
            url="https://example.com",
            response_text=json.dumps(sample_resources),
            error=None,
            access_token="test-token",
            total_count=3,
            status=200,
            results_by_url=results_by_url,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["123"],
            response_headers=None,
            storage_mode=CompressedDictStorageMode.default(),
        )
        response.remove_duplicates()
        resources = response.get_resources()
        assert isinstance(resources, FhirResourceList)
        assert len(resources) == 2

    def test_from_response(self) -> None:
        """Test creating a FhirGetListResponse from another response."""
        mock_response = Mock(spec=FhirGetResponse)
        mock_response.request_id = "test-request"
        mock_response.url = "https://example.com"
        mock_response.error = None
        mock_response.access_token = "test-token"
        mock_response.total_count = 1
        mock_response.status = 200
        mock_response.results_by_url = []
        mock_response.next_url = None
        mock_response.extra_context_to_return = {}
        mock_response.resource_type = "Patient"
        mock_response.id_ = ["123"]
        mock_response.response_headers = None
        mock_response.chunk_number = 1
        mock_response.cache_hits = 0
        mock_response.get_resources.return_value = FhirResourceList(
            [
                FhirResource(
                    initial_dict={"resourceType": "Patient", "id": "123"},
                    storage_mode=CompressedDictStorageMode.default(),
                )
            ]
        )
        mock_response.storage_mode = CompressedDictStorageMode.default()

        list_response = FhirGetListResponse.from_response(mock_response)
        assert list_response.request_id == "test-request"
        resources = list_response.get_resources()
        assert isinstance(resources, FhirResourceList)
        assert len(resources) == 1

    def test_get_bundle_entries(self, sample_resources: List[Dict[str, Any]]) -> None:
        """Test getting bundle entries."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetListResponse(
            request_id="test-request",
            url="https://example.com",
            response_text=json.dumps(sample_resources),
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
        bundle_entries = response.get_bundle_entries()
        assert len(bundle_entries) == 2
        assert isinstance(bundle_entries[0], FhirBundleEntry)
        assert isinstance(bundle_entries[1], FhirBundleEntry)
        assert bundle_entries[0].resource is not None
        assert bundle_entries[0].resource["resourceType"] == "Patient"

    def test_get_response_text(self, sample_resources: List[Dict[str, Any]]) -> None:
        """Test getting the response text as JSON."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetListResponse(
            request_id="test-request",
            url="https://example.com",
            response_text=json.dumps(sample_resources),
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
        response_text = response.get_response_text()
        assert "Patient" in response_text
        assert "Observation" in response_text

    @pytest.mark.asyncio
    async def test_consume_resource_async(
        self, sample_resources: List[Dict[str, Any]]
    ) -> None:
        """Test async generator for resources."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetListResponse(
            request_id="test-request",
            url="https://example.com",
            response_text=json.dumps(sample_resources),
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
        # Collect resources from the generator
        resources = []
        async for resource in response.consume_resource_async():
            resources.append(resource)
        assert len(resources) == 2
        assert resources[0]["resourceType"] == "Patient"
        assert resources[1]["resourceType"] == "Observation"

        assert response.get_resource_count() == 0

    def test_consume_resource(self, sample_resources: List[Dict[str, Any]]) -> None:
        """Test async generator for resources."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetListResponse(
            request_id="test-request",
            url="https://example.com",
            response_text=json.dumps(sample_resources),
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
        # Collect resources from the generator
        resources = []
        for resource in response.consume_resource():
            resources.append(resource)
        assert len(resources) == 2
        assert resources[0]["resourceType"] == "Patient"
        assert resources[1]["resourceType"] == "Observation"

        assert response.get_resource_count() == 0

    @pytest.mark.asyncio
    async def test_consume_bundle_entry_async(
        self, sample_resources: List[Dict[str, Any]]
    ) -> None:
        """Test async generator for bundle entries."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetListResponse(
            request_id="test-request",
            url="https://example.com",
            response_text=json.dumps(sample_resources),
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
        # Collect bundle entries from the generator
        bundle_entries = []
        async for entry in response.consume_bundle_entry_async():
            bundle_entries.append(entry)
        assert len(bundle_entries) == 2
        assert isinstance(bundle_entries[0], FhirBundleEntry)
        assert isinstance(bundle_entries[1], FhirBundleEntry)
        assert bundle_entries[0].resource is not None
        assert bundle_entries[1].resource is not None
        assert bundle_entries[0].resource["resourceType"] == "Patient"
        assert bundle_entries[1].resource["resourceType"] == "Observation"

        assert response.get_resource_count() == 0

    def test_consume_bundle_entry(self, sample_resources: List[Dict[str, Any]]) -> None:
        """Test async generator for bundle entries."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetListResponse(
            request_id="test-request",
            url="https://example.com",
            response_text=json.dumps(sample_resources),
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
        # Collect bundle entries from the generator
        bundle_entries = []
        for entry in response.consume_bundle_entry():
            bundle_entries.append(entry)
        assert len(bundle_entries) == 2
        assert isinstance(bundle_entries[0], FhirBundleEntry)
        assert isinstance(bundle_entries[1], FhirBundleEntry)
        assert bundle_entries[0].resource is not None
        assert bundle_entries[1].resource is not None
        assert bundle_entries[0].resource["resourceType"] == "Patient"
        assert bundle_entries[1].resource["resourceType"] == "Observation"

        assert response.get_resource_count() == 0
