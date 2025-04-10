import json
from datetime import datetime, UTC
from typing import Dict, Any, List
from unittest.mock import Mock

import pytest

from compressedfhir.fhir.fhir_bundle_entry import FhirBundleEntry
from compressedfhir.fhir.fhir_bundle_entry_request import FhirBundleEntryRequest
from compressedfhir.fhir.fhir_bundle_entry_response import (
    FhirBundleEntryResponse,
)
from compressedfhir.fhir.fhir_resource_list import FhirResourceList
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.get.fhir_get_bundle_response import (
    FhirGetBundleResponse,
)
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_url_result import (
    RetryableAioHttpUrlResult,
)


class TestFhirGetBundleResponse:
    @pytest.fixture
    def sample_bundle_response(self) -> Dict[str, Any]:
        """Fixture to provide a sample FHIR bundle response."""
        return {
            "resourceType": "Bundle",
            "id": "test-bundle-id",
            "type": "searchset",
            "total": 2,
            "timestamp": "2023-12-01T12:00:00Z",
            "entry": [
                {
                    "fullUrl": "https://example.com/Patient/123",
                    "resource": {"resourceType": "Patient", "id": "123"},
                },
                {
                    "fullUrl": "https://example.com/Observation/456",
                    "resource": {"resourceType": "Observation", "id": "456"},
                },
            ],
        }

    def test_init(self, sample_bundle_response: Dict[str, Any]) -> None:
        """Test initialization of FhirGetBundleResponse."""
        results_by_url: List[RetryableAioHttpUrlResult] = []

        response = FhirGetBundleResponse(
            request_id="test-request",
            url="https://example.com",
            response_text=json.dumps(sample_bundle_response),
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
        assert len(response.get_bundle_entries()) == 2
        assert response._bundle_metadata.id_ == "test-bundle-id"
        assert response._bundle_metadata.type_ == "searchset"

    def test_append_unique(self, sample_bundle_response: Dict[str, Any]) -> None:
        """Test appending another response."""
        results_by_url: List[RetryableAioHttpUrlResult] = []

        first_response = FhirGetBundleResponse(
            request_id="test-request-1",
            url="https://example.com",
            response_text=json.dumps(sample_bundle_response),
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

        second_response = FhirGetBundleResponse(
            request_id="test-request-2",
            url="https://example.com/next",
            response_text=json.dumps(sample_bundle_response),
            error=None,
            access_token="test-token",
            total_count=2,
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

        assert len(first_response.get_bundle_entries()) == 2

    def test_get_resources(self, sample_bundle_response: Dict[str, Any]) -> None:
        """Test getting resources from the response."""
        results_by_url: List[RetryableAioHttpUrlResult] = []

        response = FhirGetBundleResponse(
            request_id="test-request",
            url="https://example.com",
            response_text=json.dumps(sample_bundle_response),
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
        assert resources[0]["resourceType"] == "Patient"
        assert resources[1]["resourceType"] == "Observation"

    def test_remove_duplicates(self, sample_bundle_response: Dict[str, Any]) -> None:
        """Test removing duplicate resources."""
        # Add a duplicate entry to the sample bundle response
        sample_bundle_response["entry"].append(sample_bundle_response["entry"][0])

        results_by_url: List[RetryableAioHttpUrlResult] = []

        response = FhirGetBundleResponse(
            request_id="test-request",
            url="https://example.com",
            response_text=json.dumps(sample_bundle_response),
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

        assert len(response.get_bundle_entries()) == 2

    def test_from_response(self) -> None:
        """Test creating a FhirGetBundleResponse from another response."""
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
        mock_response.storage_mode = CompressedDictStorageMode.default()

        mock_response.get_bundle_entries.return_value = [
            FhirBundleEntry(
                resource={"resourceType": "Patient", "id": "123"},
                request=FhirBundleEntryRequest(url="https://example.com"),
                response=FhirBundleEntryResponse(
                    status="200", etag="test-etag", lastModified=datetime.now(UTC)
                ),
                storage_mode=CompressedDictStorageMode.default(),
            )
        ]

        bundle_response = FhirGetBundleResponse.from_response(mock_response)

        assert bundle_response.request_id == "test-request"
        assert len(bundle_response.get_bundle_entries()) == 1

    def test_create_bundle(self, sample_bundle_response: Dict[str, Any]) -> None:
        """Test creating a Bundle from the response."""
        results_by_url: List[RetryableAioHttpUrlResult] = []

        response = FhirGetBundleResponse(
            request_id="test-request",
            url="https://example.com",
            response_text=json.dumps(sample_bundle_response),
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

        bundle = response.create_bundle()

        assert bundle.total == 2
        assert bundle.id_ == "test-bundle-id"
        assert bundle.entry
        assert len(bundle.entry) == 2

    def test_sort_resources(self, sample_bundle_response: Dict[str, Any]) -> None:
        """Test sorting resources in the response."""
        results_by_url: List[RetryableAioHttpUrlResult] = []

        response = FhirGetBundleResponse(
            request_id="test-request",
            url="https://example.com",
            response_text=json.dumps(sample_bundle_response),
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

        sorted_response = response.sort_resources()

        assert isinstance(sorted_response, FhirGetBundleResponse)
        assert len(sorted_response.get_bundle_entries()) == 2

    def test_get_response_text(self, sample_bundle_response: Dict[str, Any]) -> None:
        """Test getting the response text as JSON."""
        results_by_url: List[RetryableAioHttpUrlResult] = []

        response = FhirGetBundleResponse(
            request_id="test-request",
            url="https://example.com",
            response_text=json.dumps(sample_bundle_response),
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

        assert "test-bundle-id" in response_text
        assert "Patient" in response_text
        assert "Observation" in response_text

    @pytest.mark.asyncio
    async def test_consume_resource_async(
        self, sample_bundle_response: Dict[str, Any]
    ) -> None:
        """Test async generator for resources."""
        results_by_url: List[RetryableAioHttpUrlResult] = []

        response = FhirGetBundleResponse(
            request_id="test-request",
            url="https://example.com",
            response_text=json.dumps(sample_bundle_response),
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

    def test_consume_resource(self, sample_bundle_response: Dict[str, Any]) -> None:
        """Test async generator for resources."""
        results_by_url: List[RetryableAioHttpUrlResult] = []

        response = FhirGetBundleResponse(
            request_id="test-request",
            url="https://example.com",
            response_text=json.dumps(sample_bundle_response),
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
    async def test_consume_resource_async_empty(self) -> None:
        """Test resources generator with no entries."""
        results_by_url: List[RetryableAioHttpUrlResult] = []

        response = FhirGetBundleResponse(
            request_id="test-request",
            url="https://example.com",
            response_text='{"resourceType": "Bundle", "entry": []}',
            error=None,
            access_token="test-token",
            total_count=0,
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

        assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_consume_bundle_entry_async(
        self, sample_bundle_response: Dict[str, Any]
    ) -> None:
        """Test async generator for bundle entries."""
        results_by_url: List[RetryableAioHttpUrlResult] = []

        response = FhirGetBundleResponse(
            request_id="test-request",
            url="https://example.com",
            response_text=json.dumps(sample_bundle_response),
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
        assert len(response._bundle_entries) == 0

    def test_consume_bundle_async(self, sample_bundle_response: Dict[str, Any]) -> None:
        """Test async generator for bundle entries."""
        results_by_url: List[RetryableAioHttpUrlResult] = []

        response = FhirGetBundleResponse(
            request_id="test-request",
            url="https://example.com",
            response_text=json.dumps(sample_bundle_response),
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
        assert len(response._bundle_entries) == 0

    @pytest.mark.asyncio
    async def test_consume_bundle_entry_async_empty(self) -> None:
        """Test bundle entries generator with no entries."""
        results_by_url: List[RetryableAioHttpUrlResult] = []

        response = FhirGetBundleResponse(
            request_id="test-request",
            url="https://example.com",
            response_text='{"resourceType": "Bundle", "entry": []}',
            error=None,
            access_token="test-token",
            total_count=0,
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

        assert len(bundle_entries) == 0
        assert response.get_resource_count() == 0

    @pytest.mark.asyncio
    async def test_consume_resource_async_with_none_resources(self) -> None:
        """Test resources generator with some None resources."""
        results_by_url: List[RetryableAioHttpUrlResult] = []

        # Create a response with some None resources
        response = FhirGetBundleResponse(
            request_id="test-request",
            url="https://example.com",
            response_text=json.dumps(
                {
                    "resourceType": "Bundle",
                    "entry": [
                        {"resource": {"resourceType": "Patient", "id": "123"}},
                        {"resource": None},
                        {"resource": {"resourceType": "Observation", "id": "456"}},
                    ],
                }
            ),
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

        # Collect resources from the generator
        resources = []
        async for resource in response.consume_resource_async():
            resources.append(resource)

        assert len(resources) == 2
        assert resources[0]["resourceType"] == "Patient"
        assert resources[1]["resourceType"] == "Observation"

        assert response.get_resource_count() == 0
