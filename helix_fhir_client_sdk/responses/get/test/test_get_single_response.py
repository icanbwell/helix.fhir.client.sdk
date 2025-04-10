import json
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock

import pytest

from compressedfhir.fhir.fhir_bundle_entry import (
    FhirBundleEntry,
)
from compressedfhir.fhir.fhir_resource_list import FhirResourceList
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.get.fhir_get_bundle_response import (
    FhirGetBundleResponse,
)
from helix_fhir_client_sdk.responses.get.fhir_get_single_response import (
    FhirGetSingleResponse,
)
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_url_result import (
    RetryableAioHttpUrlResult,
)


class TestFhirGetSingleResponse:
    @pytest.fixture
    def sample_single_resource(self) -> Dict[str, Any]:
        """Fixture to provide a sample FHIR single resource."""
        return {
            "resourceType": "Patient",
            "id": "123",
            "name": [{"given": ["John"], "family": "Doe"}],
        }

    def test_init(self, sample_single_resource: Dict[str, Any]) -> None:
        """Test initialization of FhirGetSingleResponse."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetSingleResponse(
            request_id="test-request",
            url="https://example.com/Patient/123",
            response_text=json.dumps(sample_single_resource),
            error=None,
            access_token="test-token",
            total_count=1,
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
        assert response.url == "https://example.com/Patient/123"

    def test_get_resources(self, sample_single_resource: Dict[str, Any]) -> None:
        """Test getting resources from the response."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetSingleResponse(
            request_id="test-request",
            url="https://example.com/Patient/123",
            response_text=json.dumps(sample_single_resource),
            error=None,
            access_token="test-token",
            total_count=1,
            status=200,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["123"],
            response_headers=None,
            results_by_url=results_by_url,
            storage_mode=CompressedDictStorageMode.default(),
        )
        resources = response.get_resources()
        assert isinstance(
            resources, FhirResourceList
        ), f"response is not a FhirResourceList but {type(response)}"
        assert len(resources) == 1
        assert resources[0]["resourceType"] == "Patient"
        assert resources[0]["id"] == "123"

    def test_get_resources_empty(self) -> None:
        """Test getting resources when no resource exists."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetSingleResponse(
            request_id="test-request",
            url="https://example.com/Patient/123",
            response_text="",
            error=None,
            access_token="test-token",
            total_count=0,
            status=200,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["123"],
            response_headers=None,
            results_by_url=results_by_url,
            storage_mode=CompressedDictStorageMode.default(),
        )
        resources = response.get_resources()
        assert isinstance(resources, FhirResourceList)
        assert len(resources) == 0

    def test_get_bundle_entry(self, sample_single_resource: Dict[str, Any]) -> None:
        """Test getting a bundle entry from the response."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetSingleResponse(
            request_id="test-request",
            url="https://example.com/Patient/123",
            response_text=json.dumps(sample_single_resource),
            error=None,
            access_token="test-token",
            total_count=1,
            status=200,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["123"],
            response_headers=None,
            results_by_url=results_by_url,
            storage_mode=CompressedDictStorageMode.default(),
        )
        assert response._resource is not None
        bundle_entry = response._create_bundle_entry(
            resource=response._resource,
        )
        assert isinstance(bundle_entry, FhirBundleEntry)
        assert bundle_entry.resource is not None
        assert bundle_entry.resource["resourceType"] == "Patient"
        assert bundle_entry.resource["id"] == "123"

    def test_get_bundle_entries(self, sample_single_resource: Dict[str, Any]) -> None:
        """Test getting bundle entries from the response."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetSingleResponse(
            request_id="test-request",
            url="https://example.com/Patient/123",
            response_text=json.dumps(sample_single_resource),
            error=None,
            access_token="test-token",
            total_count=1,
            status=200,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["123"],
            response_headers=None,
            results_by_url=results_by_url,
            storage_mode=CompressedDictStorageMode.default(),
        )
        bundle_entries = response.get_bundle_entries()
        assert len(bundle_entries) == 1
        assert isinstance(bundle_entries[0], FhirBundleEntry)
        assert bundle_entries[0].resource is not None
        assert bundle_entries[0].resource["resourceType"] == "Patient"

    def test_remove_duplicates(self, sample_single_resource: Dict[str, Any]) -> None:
        """Test removing duplicates from a single resource response."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetSingleResponse(
            request_id="test-request",
            url="https://example.com/Patient/123",
            response_text=json.dumps(sample_single_resource),
            error=None,
            access_token="test-token",
            total_count=1,
            status=200,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["123"],
            response_headers=None,
            results_by_url=results_by_url,
            storage_mode=CompressedDictStorageMode.default(),
        )
        result = response.remove_duplicates()
        assert result == response

    def test_get_response_text(self, sample_single_resource: Dict[str, Any]) -> None:
        """Test getting the response text as JSON."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetSingleResponse(
            request_id="test-request",
            url="https://example.com/Patient/123",
            response_text=json.dumps(sample_single_resource),
            error=None,
            access_token="test-token",
            total_count=1,
            status=200,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["123"],
            response_headers=None,
            results_by_url=results_by_url,
            storage_mode=CompressedDictStorageMode.default(),
        )
        response_text = response.get_response_text()
        assert "Patient" in response_text
        assert "123" in response_text

    def test_sort_resources(self, sample_single_resource: Dict[str, Any]) -> None:
        """Test sorting resources in a single resource response."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetSingleResponse(
            request_id="test-request",
            url="https://example.com/Patient/123",
            response_text=json.dumps(sample_single_resource),
            error=None,
            access_token="test-token",
            total_count=1,
            status=200,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["123"],
            response_headers=None,
            results_by_url=results_by_url,
            storage_mode=CompressedDictStorageMode.default(),
        )
        sorted_response = response.sort_resources()
        assert sorted_response == response

    def test_from_response_not_implemented(self) -> None:
        """Test that from_response raises NotImplementedError."""
        mock_response = Mock(spec=FhirGetResponse)
        with pytest.raises(NotImplementedError):
            FhirGetSingleResponse.from_response(mock_response)

    @pytest.mark.asyncio
    async def test_consume_resource_async(
        self, sample_single_resource: Dict[str, Any]
    ) -> None:
        """Test async generator for resources."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetSingleResponse(
            request_id="test-request",
            url="https://example.com/Patient/123",
            response_text=json.dumps(sample_single_resource),
            error=None,
            access_token="test-token",
            total_count=1,
            status=200,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["123"],
            response_headers=None,
            results_by_url=results_by_url,
            storage_mode=CompressedDictStorageMode.default(),
        )
        # Collect resources from the generator
        resources = []
        async for resource in response.consume_resource_async():
            resources.append(resource)
        assert len(resources) == 1
        assert resources[0]["resourceType"] == "Patient"
        assert response.get_resource_count() == 0

    def test_consume_resource(self, sample_single_resource: Dict[str, Any]) -> None:
        """Test async generator for resources."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetSingleResponse(
            request_id="test-request",
            url="https://example.com/Patient/123",
            response_text=json.dumps(sample_single_resource),
            error=None,
            access_token="test-token",
            total_count=1,
            status=200,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["123"],
            response_headers=None,
            results_by_url=results_by_url,
            storage_mode=CompressedDictStorageMode.default(),
        )
        # Collect resources from the generator
        resources = []
        for resource in response.consume_resource():
            resources.append(resource)
        assert len(resources) == 1
        assert resources[0]["resourceType"] == "Patient"
        assert response.get_resource_count() == 0

    @pytest.mark.asyncio
    async def test_consume_bundle_entry_async(
        self, sample_single_resource: Dict[str, Any]
    ) -> None:
        """Test async generator for bundle entries."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetSingleResponse(
            request_id="test-request",
            url="https://example.com/Patient/123",
            response_text=json.dumps(sample_single_resource),
            error=None,
            access_token="test-token",
            total_count=1,
            status=200,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["123"],
            response_headers=None,
            results_by_url=results_by_url,
            storage_mode=CompressedDictStorageMode.default(),
        )
        # Collect bundle entries from the generator
        bundle_entries = []
        async for entry in response.consume_bundle_entry_async():
            bundle_entries.append(entry)
        assert len(bundle_entries) == 1
        assert isinstance(bundle_entries[0], FhirBundleEntry)
        assert bundle_entries[0].resource is not None
        assert bundle_entries[0].resource["resourceType"] == "Patient"
        assert response.get_resource_count() == 0

    def test_consume_bundle_entry(self, sample_single_resource: Dict[str, Any]) -> None:
        """Test async generator for bundle entries."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetSingleResponse(
            request_id="test-request",
            url="https://example.com/Patient/123",
            response_text=json.dumps(sample_single_resource),
            error=None,
            access_token="test-token",
            total_count=1,
            status=200,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["123"],
            response_headers=None,
            results_by_url=results_by_url,
            storage_mode=CompressedDictStorageMode.default(),
        )
        # Collect bundle entries from the generator
        bundle_entries = []
        for entry in response.consume_bundle_entry():
            bundle_entries.append(entry)
        assert len(bundle_entries) == 1
        assert isinstance(bundle_entries[0], FhirBundleEntry)
        assert bundle_entries[0].resource is not None
        assert bundle_entries[0].resource["resourceType"] == "Patient"
        assert response.get_resource_count() == 0

    def test_append_method(self, sample_single_resource: Dict[str, Any]) -> None:
        """Test the _append method."""
        results_by_url: List[RetryableAioHttpUrlResult] = []
        response = FhirGetSingleResponse(
            request_id="test-request",
            url="https://example.com/Patient/123",
            response_text=json.dumps(sample_single_resource),
            error=None,
            access_token="test-token",
            total_count=1,
            status=200,
            next_url=None,
            extra_context_to_return={},
            resource_type="Patient",
            id_=["123"],
            response_headers=None,
            results_by_url=results_by_url,
            storage_mode=CompressedDictStorageMode.default(),
        )
        mock_other_response = Mock(spec=FhirGetSingleResponse)
        # implement an async generator for the mock
        mock_other_response.get_resources_generator = AsyncMock(
            return_value=iter([sample_single_resource])
        )
        mock_other_response.get_bundle_entries_generator = AsyncMock(
            return_value=iter(
                [
                    FhirBundleEntry(
                        resource=sample_single_resource,
                        fullUrl="https://example.com/Patient/123",
                        request=None,
                        response=None,
                        storage_mode=CompressedDictStorageMode.default(),
                    )
                ]
            )
        )
        mock_other_response.get_bundle_entries = Mock(
            return_value=[
                FhirBundleEntry(
                    resource=sample_single_resource,
                    fullUrl="https://example.com/Patient/123",
                    request=None,
                    response=None,
                    storage_mode=CompressedDictStorageMode.default(),
                )
            ]
        )
        mock_other_response.chunk_number = 1
        mock_other_response.results_by_url = results_by_url
        mock_other_response.resource_type = "Patient"
        mock_other_response.id_ = ["123"]
        mock_other_response.response_headers = None
        mock_other_response.error = None
        mock_other_response.total_count = 1
        mock_other_response.status = 200
        mock_other_response.next_url = None
        mock_other_response.extra_context_to_return = {}
        mock_other_response.cache_hits = 0
        mock_other_response.access_token = "test-token"
        mock_other_response.request_id = "test-request"

        appended_response = response._append(mock_other_response)
        assert isinstance(appended_response, FhirGetBundleResponse)
