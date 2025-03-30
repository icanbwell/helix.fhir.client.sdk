import json
from datetime import datetime, UTC
from typing import Dict, Any, List, AsyncGenerator

import pytest

from helix_fhir_client_sdk.fhir.bundle_entry import BundleEntry
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.structures.fhir_types import FhirResource


# Concrete implementation of FhirGetResponse for testing
class TestFhirGetResponse(FhirGetResponse):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._resources: List[FhirResource] = []
        self._bundle_entries: List[BundleEntry] = []

    def _append(self, other_response: "FhirGetResponse") -> "FhirGetResponse":
        # Simple implementation for testing
        return self

    def _extend(self, others: List["FhirGetResponse"]) -> "FhirGetResponse":
        # Simple implementation for testing
        return self

    def get_resources(self) -> List[FhirResource]:
        return self._resources

    async def get_resources_generator(self) -> AsyncGenerator[FhirResource, None]:
        for resource in self._resources:
            yield resource

    def get_bundle_entries(self) -> List[BundleEntry]:
        return self._bundle_entries

    async def get_bundle_entries_generator(self) -> AsyncGenerator[BundleEntry, None]:
        for entry in self._bundle_entries:
            yield entry

    def remove_duplicates(self) -> "FhirGetResponse":
        # Simple implementation for testing
        return self

    @classmethod
    def from_response(cls, other_response: "FhirGetResponse") -> "FhirGetResponse":
        # Simple implementation for testing
        return cls(
            request_id=other_response.request_id,
            url=other_response.url,
            error=other_response.error,
            access_token=other_response.access_token,
            total_count=other_response.total_count,
            status=other_response.status,
            next_url=other_response.next_url,
            extra_context_to_return=other_response.extra_context_to_return,
            resource_type=other_response.resource_type,
            id_=other_response.id_,
            response_headers=other_response.response_headers,
            chunk_number=other_response.chunk_number,
            cache_hits=other_response.cache_hits,
            results_by_url=other_response.results_by_url,
        )

    def get_response_text(self) -> str:
        return json.dumps(self._resources)

    def sort_resources(self) -> "FhirGetResponse":
        # Simple implementation for testing
        return self


class TestFhirGetResponseClass:
    @pytest.fixture
    def sample_response_data(self) -> Dict[str, Any]:
        return {
            "request_id": "test-request-id",
            "url": "https://example.com/fhir",
            "error": None,
            "access_token": "test-token",
            "total_count": 2,
            "status": 200,
            "next_url": None,
            "extra_context_to_return": {},
            "resource_type": "Patient",
            "id_": ["123"],
            "response_headers": [
                "Last-Modified: 2023-12-01T12:00:00Z",
                'ETag: W/"abc123"',
            ],
            "chunk_number": 1,
            "cache_hits": 0,
            "results_by_url": [],
        }

    def test_init(self, sample_response_data: Dict[str, Any]) -> None:
        """Test initialization of FhirGetResponse."""
        response = TestFhirGetResponse(**sample_response_data)

        assert response.request_id == "test-request-id"
        assert response.url == "https://example.com/fhir"
        assert response.status == 200
        assert response.successful is True

    def test_lastModified(self, sample_response_data: Dict[str, Any]) -> None:
        """Test lastModified property."""
        response = TestFhirGetResponse(**sample_response_data)

        assert response.lastModified == datetime(2023, 12, 1, 12, 0, 0, tzinfo=UTC)

    def test_etag(self, sample_response_data: Dict[str, Any]) -> None:
        """Test etag property."""
        response = TestFhirGetResponse(**sample_response_data)

        assert response.etag == 'W/"abc123"'

    def test_parse_json(self) -> None:
        """Test parse_json method."""
        # Test valid JSON
        result: Dict[str, Any] | List[Dict[str, Any]] = FhirGetResponse.parse_json(
            '{"resourceType": "Patient", "id": "123"}'
        )
        assert isinstance(result, dict)
        assert result == {"resourceType": "Patient", "id": "123"}

        # Test empty content
        result = FhirGetResponse.parse_json("")
        assert isinstance(result, dict)
        assert result["resourceType"] == "OperationOutcome"
        assert result["issue"][0]["severity"] == "error"

        # Test invalid JSON
        result = FhirGetResponse.parse_json("{invalid json")
        assert isinstance(result, dict)
        assert result["resourceType"] == "OperationOutcome"
        assert result["issue"][0]["severity"] == "error"

    @pytest.mark.asyncio
    async def test_from_async_generator(self) -> None:
        """Test from_async_generator class method."""

        async def mock_generator() -> AsyncGenerator[FhirGetResponse, None]:
            response1: FhirGetResponse = TestFhirGetResponse(
                request_id="test1",
                url="url1",
                error=None,
                access_token="token1",
                total_count=1,
                status=200,
                next_url=None,
                extra_context_to_return={},
                resource_type="Patient",
                id_=["1"],
                response_headers=None,
                chunk_number=1,
                cache_hits=0,
                results_by_url=[],
            )
            response2: FhirGetResponse = TestFhirGetResponse(
                request_id="test2",
                url="url2",
                error=None,
                access_token="token2",
                total_count=1,
                status=200,
                next_url=None,
                extra_context_to_return={},
                resource_type="Observation",
                id_=["2"],
                response_headers=None,
                chunk_number=2,
                cache_hits=0,
                results_by_url=[],
            )
            yield response1
            yield response2

        result: FhirGetResponse | None = await TestFhirGetResponse.from_async_generator(
            mock_generator()
        )
        assert result is not None
        assert result.request_id == "test2"  # Last response in the generator

    def test_get_operation_outcomes(self, sample_response_data: Dict[str, Any]) -> None:
        """Test get_operation_outcomes method."""
        response = TestFhirGetResponse(**sample_response_data)
        response._resources = [
            FhirResource(
                initial_dict={"resourceType": "OperationOutcome", "issue": []},
                storage_mode="compressed_msgpack",
            ),
            FhirResource(
                initial_dict={"resourceType": "Patient", "id": "123"},
                storage_mode="compressed_msgpack",
            ),
        ]

        outcomes = response.get_operation_outcomes()
        assert len(outcomes) == 1
        assert outcomes[0]["resourceType"] == "OperationOutcome"

    def test_get_resources_except_operation_outcomes(
        self, sample_response_data: Dict[str, Any]
    ) -> None:
        """Test get_resources_except_operation_outcomes method."""
        response = TestFhirGetResponse(**sample_response_data)
        response._resources = [
            FhirResource(
                initial_dict={"resourceType": "OperationOutcome", "issue": []},
                storage_mode="compressed_msgpack",
            ),
            FhirResource(
                initial_dict={"resourceType": "Patient", "id": "123"},
                storage_mode="compressed_msgpack",
            ),
        ]

        resources = response.get_resources_except_operation_outcomes()
        assert len(resources) == 1
        assert resources[0]["resourceType"] == "Patient"

    def test_has_resources(self, sample_response_data: Dict[str, Any]) -> None:
        """Test has_resources method."""
        response = TestFhirGetResponse(**sample_response_data)

        # No resources
        assert not response.has_resources()

        # With resources
        response._resources = [
            FhirResource(
                initial_dict={"resourceType": "Patient", "id": "123"},
                storage_mode="compressed_msgpack",
            )
        ]
        assert response.has_resources()

    def test_to_dict(self, sample_response_data: Dict[str, Any]) -> None:
        """Test to_dict method."""
        response = TestFhirGetResponse(**sample_response_data)
        response_dict = response.to_dict()

        assert isinstance(response_dict, dict)
        assert response_dict["request_id"] == "test-request-id"
