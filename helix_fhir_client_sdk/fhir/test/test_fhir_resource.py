import json
from typing import Dict, Any

from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)


class TestFhirResource:
    def test_init_empty(self) -> None:
        """Test initializing FhirResource with no initial dictionary."""
        resource = FhirResource(storage_mode=CompressedDictStorageMode())
        assert len(resource) == 0
        assert resource.resource_type is None
        assert resource.id is None
        assert resource.resource_type_and_id is None

    def test_init_with_data(self) -> None:
        """Test initializing FhirResource with a dictionary."""
        initial_data: Dict[str, Any] = {
            "resourceType": "Patient",
            "id": "123",
            "name": [{"given": ["John"]}],
        }
        resource = FhirResource(
            initial_dict=initial_data, storage_mode=CompressedDictStorageMode()
        )

        with resource.transaction():
            assert resource.resource_type == "Patient"
            assert resource.id == "123"
            assert resource.resource_type_and_id == "Patient/123"
            assert resource["name"][0]["given"][0] == "John"

    def test_resource_type_and_id_property(self) -> None:
        """Test resource_type_and_id property with various scenarios."""
        # Scenario 1: Both resource type and id present
        resource1 = FhirResource(
            initial_dict={"resourceType": "Observation", "id": "456"},
            storage_mode=CompressedDictStorageMode(),
        )
        assert resource1.resource_type_and_id == "Observation/456"

        # Scenario 2: Missing resource type
        resource2 = FhirResource(
            initial_dict={"id": "789"}, storage_mode=CompressedDictStorageMode()
        )
        assert resource2.resource_type_and_id is None

        # Scenario 3: Missing id
        resource3 = FhirResource(
            initial_dict={"resourceType": "Patient"},
            storage_mode=CompressedDictStorageMode(),
        )
        assert resource3.resource_type_and_id is None

    def test_equality(self) -> None:
        """Test equality comparison between FhirResource instances."""
        # Scenario 1: Equal resources
        resource1 = FhirResource(
            initial_dict={"resourceType": "Patient", "id": "123"},
            storage_mode=CompressedDictStorageMode(),
        )
        resource2 = FhirResource(
            initial_dict={"resourceType": "Patient", "id": "123"},
            storage_mode=CompressedDictStorageMode(),
        )
        assert resource1 == resource2

        # Scenario 2: Different resource types
        resource3 = FhirResource(
            initial_dict={"resourceType": "Observation", "id": "123"},
            storage_mode=CompressedDictStorageMode(),
        )
        assert resource1 != resource3

        # Scenario 3: Different ids
        resource4 = FhirResource(
            initial_dict={"resourceType": "Patient", "id": "456"},
            storage_mode=CompressedDictStorageMode(),
        )
        assert resource1 != resource4

        # Scenario 4: Comparing with non-FhirResource
        assert resource1 != "Not a FhirResource"

    def test_to_json(self) -> None:
        """Test JSON serialization of FhirResource."""
        initial_data: Dict[str, Any] = {
            "resourceType": "Patient",
            "id": "123",
            "name": [{"given": ["John"]}],
        }
        resource = FhirResource(
            initial_dict=initial_data, storage_mode=CompressedDictStorageMode()
        )

        json_str = resource.to_json()
        parsed_json = json.loads(json_str)

        assert parsed_json == initial_data
        assert "resourceType" in parsed_json
        assert "id" in parsed_json
