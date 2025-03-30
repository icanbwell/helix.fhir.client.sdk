import json
from typing import List

import pytest

from helix_fhir_client_sdk.fhir.bundle import Bundle
from helix_fhir_client_sdk.fhir.bundle_entry import BundleEntry
from helix_fhir_client_sdk.fhir_bundle_appender import FhirBundleAppender
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.get_responses.fhir_get_bundle_response import (
    FhirGetBundleResponse,
)
from helix_fhir_client_sdk.structures.fhir_types import FhirResource


class TestFhirBundleAppender:
    @pytest.fixture
    def sample_fhir_get_response(self) -> FhirGetResponse:
        """Fixture to create a sample FhirGetResponse."""
        mock_response = FhirGetBundleResponse(
            request_id="test-request",
            url="https://example.com/Patient",
            response_text=json.dumps(
                {
                    "resourceType": "Bundle",
                    "entry": [{"resource": {"resourceType": "Patient", "id": "123"}}],
                }
            ),
            error=None,
            access_token="test-token",
            total_count=1,
            status=200,
            resource_type="Patient",
            id_=["123"],
            next_url=None,
            extra_context_to_return={},
            response_headers=["Content-Type: application/json"],
            chunk_number=None,
            cache_hits=None,
            results_by_url=[],
            storage_mode="compressed_msgpack",
        )
        return mock_response

    @pytest.fixture
    def sample_bundle(self) -> Bundle:
        """Fixture to create a sample Bundle."""
        return Bundle(type_="collection", total=0, entry=[])

    def test_append_responses(
        self, sample_fhir_get_response: FhirGetResponse, sample_bundle: Bundle
    ) -> None:
        """Test appending responses to a bundle."""
        responses = [sample_fhir_get_response]
        updated_bundle = FhirBundleAppender.append_responses(
            responses=responses, bundle=sample_bundle, storage_mode="compressed_msgpack"
        )

        assert updated_bundle.entry is not None
        assert len(updated_bundle.entry) == 1
        assert updated_bundle.entry[0].resource is not None
        assert updated_bundle.entry[0].resource["resourceType"] == "Patient"

    def test_add_operation_outcomes_to_response(
        self, sample_fhir_get_response: FhirGetResponse
    ) -> None:
        """Test adding operation outcomes to a response."""
        bundle_entries = FhirBundleAppender.add_operation_outcomes_to_response(
            response=sample_fhir_get_response, storage_mode="compressed_msgpack"
        )

        assert len(bundle_entries) == 1
        assert bundle_entries[0].resource is not None
        assert bundle_entries[0].resource["resourceType"] == "Patient"

    def test_create_operation_outcome_resource(self) -> None:
        """Test creating an operation outcome resource."""
        operation_outcome = FhirBundleAppender.create_operation_outcome_resource(
            error="Test error",
            url="https://example.com/Patient",
            resource_type="Patient",
            id_="123",
            status=404,
            access_token="test-token",
            extra_context_to_return={},
            request_id="test-request",
            storage_mode="compressed_msgpack",
        )

        assert operation_outcome["resourceType"] == "OperationOutcome"
        with operation_outcome.transaction():
            assert operation_outcome["issue"][0]["severity"] == "error"
            assert operation_outcome["issue"][0]["code"] == "not-found"

    def test_get_diagnostic_coding(self) -> None:
        """Test generating diagnostic coding."""
        diagnostics = FhirBundleAppender.get_diagnostic_coding(
            url="https://example.com/Patient",
            resource_type="Patient",
            id_="123",
            status=200,
            access_token="test-token",
        )

        assert len(diagnostics) == 5
        assert any(d["system"] == "https://www.icanbwell.com/url" for d in diagnostics)
        assert any(
            d["system"] == "https://www.icanbwell.com/resourceType" for d in diagnostics
        )

    def test_remove_duplicate_resources(self) -> None:
        """Test removing duplicate resources from a bundle."""
        bundle = Bundle(
            type_="collection",
            entry=[
                BundleEntry(
                    resource={"resourceType": "Patient", "id": "123"},
                    request=None,
                    response=None,
                ),
                BundleEntry(
                    resource={"resourceType": "Patient", "id": "123"},
                    request=None,
                    response=None,
                ),
                BundleEntry(
                    resource={"resourceType": "Observation", "id": "456"},
                    request=None,
                    response=None,
                ),
            ],
        )

        updated_bundle = FhirBundleAppender.remove_duplicate_resources(bundle=bundle)

        assert updated_bundle.entry is not None
        assert len(updated_bundle.entry) == 2
        resource_types = [
            entry.resource["resourceType"]
            for entry in updated_bundle.entry
            if entry.resource is not None
        ]
        assert set(resource_types) == {"Patient", "Observation"}

    def test_sort_resources(self) -> None:
        """Test sorting resources in a bundle."""
        bundle = Bundle(
            type_="collection",
            entry=[
                BundleEntry(
                    resource={"resourceType": "Patient", "id": "456"},
                    request=None,
                    response=None,
                ),
                BundleEntry(
                    resource={"resourceType": "Patient", "id": "123"},
                    request=None,
                    response=None,
                ),
                BundleEntry(
                    resource={"resourceType": "Observation", "id": "789"},
                    request=None,
                    response=None,
                ),
            ],
        )

        sorted_bundle = FhirBundleAppender.sort_resources(bundle=bundle)

        assert sorted_bundle.entry is not None
        assert len(sorted_bundle.entry) == 3
        sorted_ids = [
            (
                entry.resource.get("resourceType", "")
                + "/"
                + entry.resource.get("id", "")
            )
            for entry in sorted_bundle.entry
            if entry.resource is not None
        ]
        assert sorted_ids == ["Observation/789", "Patient/123", "Patient/456"]

    def test_sort_resources_with_custom_sort(self) -> None:
        """Test sorting resources with a custom sort function."""
        bundle = Bundle(
            type_="collection",
            entry=[
                BundleEntry(
                    resource={
                        "resourceType": "Patient",
                        "id": "456",
                        "name": "Charlie",
                    },
                    request=None,
                    response=None,
                ),
                BundleEntry(
                    resource={"resourceType": "Patient", "id": "123", "name": "Alice"},
                    request=None,
                    response=None,
                ),
                BundleEntry(
                    resource={"resourceType": "Patient", "id": "789", "name": "Bob"},
                    request=None,
                    response=None,
                ),
            ],
        )

        sorted_bundle = FhirBundleAppender.sort_resources(
            bundle=bundle,
            fn_sort=lambda e: e.resource.get("name", "") if e.resource else "",
        )

        assert sorted_bundle.entry is not None
        sorted_names = [
            entry.resource["name"]
            for entry in sorted_bundle.entry
            if entry.resource is not None
        ]
        assert sorted_names == ["Alice", "Bob", "Charlie"]

    def test_sort_resources_in_list(self) -> None:
        """Test sorting resources in a list."""
        resources: List[FhirResource] = [
            FhirResource(
                initial_dict={"resourceType": "Patient", "id": "456"},
                storage_mode="compressed_msgpack",
            ),
            FhirResource(
                initial_dict={"resourceType": "Patient", "id": "123"},
                storage_mode="compressed_msgpack",
            ),
            FhirResource(
                initial_dict={"resourceType": "Observation", "id": "789"},
                storage_mode="compressed_msgpack",
            ),
        ]

        sorted_resources: List[FhirResource] = (
            FhirBundleAppender.sort_resources_in_list(
                resources=resources,
            )
        )

        sorted_ids = [
            (resource.get("resourceType", "") + "/" + resource.get("id", ""))
            for resource in sorted_resources
        ]
        assert sorted_ids == ["Observation/789", "Patient/123", "Patient/456"]
