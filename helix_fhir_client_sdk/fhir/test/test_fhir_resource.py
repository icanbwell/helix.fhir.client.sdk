import json
from typing import Dict, Any, List

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

    def test_remove_none_values_from_dict_single_level(self) -> None:
        # Test removing None values from a simple dictionary
        input_dict = {"name": "John", "age": 30, "email": None, "phone": None}
        expected_output = {"name": "John", "age": 30}

        result = FhirResource.remove_none_values_from_dict(input_dict)
        assert result == expected_output

    def test_remove_none_values_from_dict_nested(self) -> None:
        # Test removing None values from a nested dictionary
        input_dict = {
            "patient": {
                "name": "Jane",
                "contact": None,
                "address": {"street": "123 Main St", "city": None},
            },
            "test_results": None,
        }
        expected_output = {
            "patient": {"name": "Jane", "address": {"street": "123 Main St"}}
        }

        result = FhirResource.remove_none_values_from_dict(input_dict)
        assert result == expected_output

    def test_remove_none_values_from_dict_or_list_with_list(self) -> None:
        # Test removing None values from a list of dictionaries
        input_list: List[Dict[str, Any]] = [
            {"name": "Alice", "age": 25},
            {"name": "Bob", "age": None},
            {"name": None, "city": "New York"},
        ]
        expected_output = [
            {"name": "Alice", "age": 25},
            {"name": "Bob"},
            {"city": "New York"},
        ]

        result = FhirResource.remove_none_values_from_dict_or_list(input_list)
        assert result == expected_output

    def test_remove_none_values_from_dict_or_list_with_nested_complex_structure(
        self,
    ) -> None:
        # Test with a more complex nested structure
        input_dict = {
            "users": [
                {
                    "id": 1,
                    "name": "John",
                    "details": {"email": None, "phone": "123-456-7890"},
                    "links": [
                        {"url": "http://example.com", "active": None},
                        {"url": None, "active": True},
                        None,
                    ],
                },
                {"id": 2, "name": None, "details": None},
            ],
            "metadata": None,
        }

        expected_output = {
            "users": [
                {
                    "id": 1,
                    "name": "John",
                    "details": {"phone": "123-456-7890"},
                    "links": [
                        {"url": "http://example.com"},
                        {"active": True},
                    ],
                },
                {
                    "id": 2,
                },
            ],
        }

        result = FhirResource.remove_none_values_from_dict_or_list(input_dict)
        assert result == expected_output
