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


class TestFhirResourceRemoveNulls:
    def test_remove_nulls_simple_dict(self) -> None:
        """
        Test removing None values from a simple dictionary
        """
        initial_dict: Dict[str, Any] = {
            "name": "John Doe",
            "age": None,
            "active": True,
            "email": None,
        }
        resource = FhirResource(initial_dict=initial_dict)
        resource.remove_nulls()

        with resource.transaction():
            # Check that None values are removed
            assert "age" not in resource
            assert "email" not in resource
            assert resource.get("name") == "John Doe"
            assert resource.get("active") is True

    def test_remove_nulls_nested_dict(self) -> None:
        """
        Test removing None values from a nested dictionary
        """
        initial_dict: Dict[str, Any] = {
            "patient": {
                "name": "Jane Smith",
                "contact": None,
                "address": {"street": None, "city": "New York"},
            },
            "status": None,
        }
        resource = FhirResource(initial_dict=initial_dict)
        resource.remove_nulls()

        with resource.transaction():
            assert "status" not in resource
            assert "contact" not in resource.get("patient", {})
            assert resource.get("patient", {}).get("address", {}).get("street") is None
            assert (
                resource.get("patient", {}).get("address", {}).get("city") == "New York"
            )

    def test_remove_nulls_list_of_dicts(self) -> None:
        """
        Test removing None values from a list of dictionaries
        """
        initial_dict: Dict[str, Any] = {
            "patients": [
                {"name": "Alice", "age": None},
                {"name": "Bob", "age": 30},
                {"name": None, "active": False},
            ]
        }
        resource = FhirResource(initial_dict=initial_dict)
        resource.remove_nulls()

        with resource.transaction():
            assert len(resource.get("patients", [])) == 3
            assert resource.get("patients", [])[0].get("name") == "Alice"
            assert resource.get("patients", [])[1].get("name") == "Bob"
            assert resource.get("patients", [])[1].get("age") == 30

    def test_remove_nulls_empty_dict(self) -> None:
        """
        Test removing None values from an empty dictionary
        """
        resource = FhirResource(initial_dict={})
        resource.remove_nulls()

        assert len(resource) == 0

    def test_remove_nulls_no_changes(self) -> None:
        """
        Test removing None values when no None values exist
        """
        initial_dict: Dict[str, Any] = {
            "name": "Test User",
            "active": True,
            "score": 100,
        }
        resource = FhirResource(initial_dict=initial_dict)
        original_dict = resource.copy()
        resource.remove_nulls()

        assert resource == original_dict

    def test_remove_nulls_with_custom_storage_mode(self) -> None:
        """
        Test removing None values with a custom storage mode
        """
        initial_dict: Dict[str, Any] = {
            "name": "Custom Mode User",
            "email": None,
            "active": True,
        }
        resource = FhirResource(
            initial_dict=initial_dict, storage_mode=CompressedDictStorageMode.default()
        )
        resource.remove_nulls()

        with resource.transaction():
            assert "email" not in resource
            assert resource.get("name") == "Custom Mode User"
            assert resource.get("active") is True

    def test_remove_nulls_preserves_false_and_zero_values(self) -> None:
        """
        Test that False and 0 values are not removed
        """
        initial_dict: Dict[str, Any] = {"active": False, "score": 0, "name": None}
        resource = FhirResource(initial_dict=initial_dict)
        resource.remove_nulls()

        with resource.transaction():
            assert resource.get("active") is False
            assert resource.get("score") == 0
            assert "name" not in resource
