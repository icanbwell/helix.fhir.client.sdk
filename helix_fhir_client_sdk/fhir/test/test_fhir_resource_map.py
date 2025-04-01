import pytest
import json

from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource
from helix_fhir_client_sdk.fhir.fhir_resource_list import FhirResourceList
from helix_fhir_client_sdk.fhir.fhir_resource_map import FhirResourceMap
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)


class TestFhirResourceMap:
    def test_init_empty(self) -> None:
        """Test initialization with no initial dictionary."""
        resource_map = FhirResourceMap()
        assert resource_map._resource_map == {}

    def test_init_with_initial_dict(self) -> None:
        """Test initialization with an initial dictionary."""
        initial_dict = {
            "Patient": FhirResourceList(
                [
                    FhirResource(
                        {"id": "123", "resourceType": "Patient"},
                        storage_mode=CompressedDictStorageMode(),
                    )
                ]
            ),
            "Observation": FhirResourceList(
                [
                    FhirResource(
                        {"id": "456", "resourceType": "Observation"},
                        storage_mode=CompressedDictStorageMode(),
                    )
                ]
            ),
        }
        resource_map = FhirResourceMap(initial_dict=initial_dict)
        assert resource_map._resource_map == initial_dict

    def test_to_dict(self) -> None:
        """Test conversion of resource map to dictionary."""
        patient_resource = {"id": "123", "resourceType": "Patient"}
        initial_dict = {
            "Patient": FhirResourceList(
                [
                    FhirResource(
                        patient_resource, storage_mode=CompressedDictStorageMode()
                    )
                ]
            )
        }
        resource_map = FhirResourceMap(initial_dict=initial_dict)
        result = resource_map.to_dict()
        assert result == {"Patient": [patient_resource]}

    def test_get_existing_resource_type(self) -> None:
        """Test getting resources for an existing resource type."""
        patient_resources = FhirResourceList(
            [
                FhirResource(
                    {"id": "123", "resourceType": "Patient"},
                    storage_mode=CompressedDictStorageMode(),
                )
            ]
        )
        initial_dict = {"Patient": patient_resources}
        resource_map = FhirResourceMap(initial_dict=initial_dict)

        result = resource_map.get(resource_type="Patient")
        assert result == patient_resources

    def test_get_nonexistent_resource_type(self) -> None:
        """Test getting resources for a non-existent resource type."""
        resource_map = FhirResourceMap()
        result = resource_map.get(resource_type="Patient")
        assert result is None

    def test_setitem(self) -> None:
        """Test setting an item in the resource map."""
        resource_map = FhirResourceMap()
        patient_resources = FhirResourceList(
            [
                FhirResource(
                    {"id": "123", "resourceType": "Patient"},
                    storage_mode=CompressedDictStorageMode(),
                )
            ]
        )
        resource_map["Patient"] = patient_resources

        assert resource_map._resource_map["Patient"] == patient_resources

    def test_getitem(self) -> None:
        """Test getting an item from the resource map."""
        patient_resources = FhirResourceList(
            [
                FhirResource(
                    {"id": "123", "resourceType": "Patient"},
                    storage_mode=CompressedDictStorageMode(),
                )
            ]
        )
        resource_map = FhirResourceMap(initial_dict={"Patient": patient_resources})

        result = resource_map["Patient"]
        assert result == patient_resources

    def test_delitem(self) -> None:
        """Test deleting an item from the resource map."""
        patient_resources = FhirResourceList(
            [
                FhirResource(
                    {"id": "123", "resourceType": "Patient"},
                    storage_mode=CompressedDictStorageMode(),
                )
            ]
        )
        resource_map = FhirResourceMap(initial_dict={"Patient": patient_resources})

        del resource_map["Patient"]
        assert "Patient" not in resource_map._resource_map

    def test_delitem_nonexistent(self) -> None:
        """Test deleting a non-existent item raises KeyError."""
        resource_map = FhirResourceMap()
        with pytest.raises(KeyError):
            del resource_map["Patient"]

    def test_contains(self) -> None:
        """Test checking if a resource type exists in the map."""
        patient_resources = FhirResourceList(
            [
                FhirResource(
                    {"id": "123", "resourceType": "Patient"},
                    storage_mode=CompressedDictStorageMode(),
                )
            ]
        )
        resource_map = FhirResourceMap(initial_dict={"Patient": patient_resources})

        assert "Patient" in resource_map
        assert "Observation" not in resource_map

    def test_items(self) -> None:
        """Test getting all items from the resource map."""
        patient_resources = FhirResourceList(
            [
                FhirResource(
                    {"id": "123", "resourceType": "Patient"},
                    storage_mode=CompressedDictStorageMode(),
                )
            ]
        )
        obs_resources = FhirResourceList(
            [
                FhirResource(
                    {"id": "456", "resourceType": "Observation"},
                    storage_mode=CompressedDictStorageMode(),
                )
            ]
        )
        initial_dict = {"Patient": patient_resources, "Observation": obs_resources}
        resource_map = FhirResourceMap(initial_dict=initial_dict)

        items = resource_map.items()
        assert len(items) == 2
        assert ("Patient", patient_resources) in items
        assert ("Observation", obs_resources) in items

    def test_get_resource_count(self) -> None:
        """Test getting the total number of resources."""
        initial_dict = {
            "Patient": FhirResourceList(
                [
                    FhirResource({"id": "1"}, storage_mode=CompressedDictStorageMode()),
                    FhirResource({"id": "2"}, storage_mode=CompressedDictStorageMode()),
                ]
            ),
            "Observation": FhirResourceList(
                [FhirResource({"id": "3"}, storage_mode=CompressedDictStorageMode())]
            ),
        }
        resource_map = FhirResourceMap(initial_dict=initial_dict)

        assert resource_map.get_resource_count() == 3

    def test_clear(self) -> None:
        """Test clearing the resource map."""
        patient_resources = FhirResourceList(
            [
                FhirResource(
                    {"id": "123", "resourceType": "Patient"},
                    storage_mode=CompressedDictStorageMode(),
                )
            ]
        )
        resource_map = FhirResourceMap(initial_dict={"Patient": patient_resources})

        resource_map.clear()
        assert len(resource_map._resource_map) == 0

    def test_get_resource_type_and_ids(self) -> None:
        """Test getting resource type and IDs."""
        initial_dict = {
            "Patient": FhirResourceList(
                [
                    FhirResource(
                        {"id": "123"}, storage_mode=CompressedDictStorageMode()
                    ),
                    FhirResource(
                        {"id": "456"}, storage_mode=CompressedDictStorageMode()
                    ),
                ]
            ),
            "Observation": FhirResourceList(
                [FhirResource({"id": "789"}, storage_mode=CompressedDictStorageMode())]
            ),
        }
        resource_map = FhirResourceMap(initial_dict=initial_dict)

        result = resource_map.get_resource_type_and_ids()
        assert set(result) == {"Patient/123", "Patient/456", "Observation/789"}

    def test_get_operation_outcomes(self) -> None:
        """Test getting operation outcomes."""
        op_outcomes = FhirResourceList(
            [FhirResource({"id": "op1"}, storage_mode=CompressedDictStorageMode())]
        )
        initial_dict = {"OperationOutcome": op_outcomes}
        resource_map = FhirResourceMap(initial_dict=initial_dict)

        result = resource_map.get_operation_outcomes()
        assert result == op_outcomes

    def test_get_operation_outcomes_empty(self) -> None:
        """Test getting operation outcomes when none exist."""
        resource_map = FhirResourceMap()
        result = resource_map.get_operation_outcomes()
        assert result == FhirResourceList()

    def test_get_resources_except_operation_outcomes(self) -> None:
        """Test getting resources excluding operation outcomes."""
        initial_dict = {
            "Patient": FhirResourceList(
                [FhirResource({"id": "123"}, storage_mode=CompressedDictStorageMode())]
            ),
            "OperationOutcome": FhirResourceList(
                [FhirResource({"id": "op1"}, storage_mode=CompressedDictStorageMode())]
            ),
            "Observation": FhirResourceList(
                [FhirResource({"id": "456"}, storage_mode=CompressedDictStorageMode())]
            ),
        }
        resource_map = FhirResourceMap(initial_dict=initial_dict)

        result = resource_map.get_resources_except_operation_outcomes()
        assert len(result) == 2
        assert all(
            resource.get("resourceType") != "OperationOutcome" for resource in result
        )

    def test_to_json(self) -> None:
        """Test converting resource map to JSON."""
        initial_dict = {
            "Patient": FhirResourceList(
                [
                    FhirResource(
                        {"id": "123", "resourceType": "Patient"},
                        storage_mode=CompressedDictStorageMode(),
                    )
                ]
            )
        }
        resource_map = FhirResourceMap(initial_dict=initial_dict)

        json_str = resource_map.to_json()
        parsed_json = json.loads(json_str)
        assert parsed_json == {"Patient": [{"id": "123", "resourceType": "Patient"}]}

    def test_get_count_of_resource_types(self) -> None:
        """Test getting the count of unique resource types."""
        initial_dict = {
            "Patient": FhirResourceList(
                [FhirResource({"id": "123"}, storage_mode=CompressedDictStorageMode())]
            ),
            "Observation": FhirResourceList(
                [FhirResource({"id": "456"}, storage_mode=CompressedDictStorageMode())]
            ),
        }
        resource_map = FhirResourceMap(initial_dict=initial_dict)

        assert resource_map.get_count_of_resource_types() == 2
