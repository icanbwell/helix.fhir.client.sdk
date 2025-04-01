import json

from helix_fhir_client_sdk.fhir.fhir_bundle import FhirBundle
from helix_fhir_client_sdk.fhir.fhir_bundle_entry import FhirBundleEntry
from helix_fhir_client_sdk.fhir.fhir_bundle_entry_list import FhirBundleEntryList
from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)


class TestBundle:
    def test_init_minimal(self) -> None:
        """Test initialization with minimal parameters."""
        bundle = FhirBundle(type_="searchset")
        assert bundle.type_ == "searchset"
        assert bundle.entry is None
        assert bundle.total is None
        assert bundle.id_ is None
        assert bundle.timestamp is None

    def test_init_full(self) -> None:
        """Test initialization with all parameters."""
        entries = FhirBundleEntryList(
            [
                FhirBundleEntry(
                    resource={"resourceType": "Patient"},
                    request=None,
                    response=None,
                    storage_mode=CompressedDictStorageMode(),
                ),
                FhirBundleEntry(
                    resource={"resourceType": "Observation"},
                    request=None,
                    response=None,
                    storage_mode=CompressedDictStorageMode(),
                ),
            ]
        )
        bundle = FhirBundle(
            type_="searchset",
            entry=entries,
            total=2,
            id_="test-bundle",
            timestamp="2023-12-01T12:00:00Z",
        )
        assert bundle.type_ == "searchset"
        assert bundle.entry is not None
        assert len(bundle.entry) == 2
        assert bundle.total == 2
        assert bundle.id_ == "test-bundle"
        assert bundle.timestamp == "2023-12-01T12:00:00Z"

    def test_to_dict_minimal(self) -> None:
        """Test converting to dictionary with minimal parameters."""
        bundle = FhirBundle(type_="searchset")
        result = bundle.to_dict()
        assert result == {"type": "searchset", "resourceType": "Bundle"}

    def test_to_dict_full(self) -> None:
        """Test converting to dictionary with all parameters."""
        entries = FhirBundleEntryList(
            [
                FhirBundleEntry(
                    resource={"resourceType": "Patient"},
                    request=None,
                    response=None,
                    storage_mode=CompressedDictStorageMode(),
                ),
                FhirBundleEntry(
                    resource={"resourceType": "Observation"},
                    request=None,
                    response=None,
                    storage_mode=CompressedDictStorageMode(),
                ),
            ]
        )
        bundle = FhirBundle(
            type_="searchset",
            entry=entries,
            total=2,
            id_="test-bundle",
            timestamp="2023-12-01T12:00:00Z",
        )
        result = bundle.to_dict()
        assert result == {
            "type": "searchset",
            "resourceType": "Bundle",
            "id": "test-bundle",
            "timestamp": "2023-12-01T12:00:00Z",
            "total": 2,
            "entry": [
                {"resource": {"resourceType": "Patient"}},
                {"resource": {"resourceType": "Observation"}},
            ],
        }

    def test_to_json(self) -> None:
        """Test converting Bundle to JSON."""
        entries = FhirBundleEntryList(
            [
                FhirBundleEntry(
                    resource={"resourceType": "Patient"},
                    request=None,
                    response=None,
                    storage_mode=CompressedDictStorageMode(),
                ),
                FhirBundleEntry(
                    resource={"resourceType": "Observation"},
                    request=None,
                    response=None,
                    storage_mode=CompressedDictStorageMode(),
                ),
            ]
        )
        bundle = FhirBundle(
            type_="searchset",
            entry=entries,
            total=2,
            id_="test-bundle",
            timestamp="2023-12-01T12:00:00Z",
        )
        json_str = bundle.to_json()
        parsed_json = json.loads(json_str)
        assert parsed_json["type"] == "searchset"
        assert parsed_json["resourceType"] == "Bundle"

    def test_add_diagnostics_to_operation_outcomes(self) -> None:
        """Test adding diagnostics to OperationOutcome resources."""
        resource = FhirResource(
            initial_dict={
                "resourceType": "OperationOutcome",
                "issue": [{"severity": "error", "details": {}}],
            },
            storage_mode=CompressedDictStorageMode(),
        )
        diagnostics_coding = [{"code": "test-code"}]

        updated_resource = FhirBundle.add_diagnostics_to_operation_outcomes(
            resource=resource, diagnostics_coding=diagnostics_coding
        )

        with updated_resource.transaction():
            assert (
                updated_resource["issue"][0]["details"]["coding"] == diagnostics_coding
            )


class TestFhirBundleCopy:
    def test_copy_full_bundle(self) -> None:
        """
        Test copying a fully populated FhirBundle
        """
        # Create a mock FhirBundleEntryList
        mock_entry_list = FhirBundleEntryList()
        mock_resource = FhirBundleEntry(
            resource=FhirResource({"resourceType": "Patient", "id": "123"})
        )
        mock_entry_list.append(mock_resource)

        # Create original bundle
        original_bundle = FhirBundle(
            id_="test-bundle-id",
            timestamp="2023-01-01T00:00:00Z",
            type_="transaction",
            entry=mock_entry_list,
            total=1,
        )

        # Create a copy
        copied_bundle = original_bundle.copy()

        # Assert that the copied bundle has the same attributes
        assert copied_bundle.id_ == original_bundle.id_
        assert copied_bundle.timestamp == original_bundle.timestamp
        assert copied_bundle.type_ == original_bundle.type_
        assert copied_bundle.total == original_bundle.total

        # Ensure the entry list is a copy, not the same object
        assert copied_bundle.entry is not original_bundle.entry
        assert copied_bundle.entry is not None
        assert original_bundle.entry is not None
        assert len(copied_bundle.entry) == len(original_bundle.entry)
        assert copied_bundle.entry[0].to_dict() == original_bundle.entry[0].to_dict()

    def test_copy_empty_bundle(self) -> None:
        """
        Test copying a bundle with no entries
        """
        # Create an empty bundle
        original_bundle = FhirBundle(type_="batch", entry=None, total=None)

        # Create a copy
        copied_bundle = original_bundle.copy()

        # Assert that the copied bundle has the same attributes
        assert copied_bundle.id_ is None
        assert copied_bundle.timestamp is None
        assert copied_bundle.type_ == "batch"
        assert copied_bundle.total is None
        assert copied_bundle.entry is None

    def test_copy_modifying_original_does_not_affect_copy(self) -> None:
        """
        Test that modifying the original bundle does not affect the copy
        """
        # Create a mock FhirBundleEntryList
        mock_entry_list = FhirBundleEntryList()
        mock_resource = FhirResource({"resourceType": "Patient", "id": "123"})
        mock_entry_list.append(FhirBundleEntry(resource=mock_resource))

        # Create original bundle
        original_bundle = FhirBundle(
            id_="test-bundle-id",
            timestamp="2023-01-01T00:00:00Z",
            type_="transaction",
            entry=mock_entry_list,
            total=1,
        )

        # Create a copy
        copied_bundle = original_bundle.copy()

        # Modify the original bundle
        original_bundle.id_ = "modified-id"
        original_bundle.timestamp = "2023-02-01T00:00:00Z"
        original_bundle.total = 2

        # Assert that the copied bundle remains unchanged
        assert copied_bundle.id_ == "test-bundle-id"
        assert copied_bundle.timestamp == "2023-01-01T00:00:00Z"
        assert copied_bundle.total == 1

    def test_copy_returns_new_instance(self) -> None:
        """
        Test that copy() returns a new FhirBundle instance
        """
        # Create a bundle
        original_bundle = FhirBundle(type_="batch")

        # Create a copy
        copied_bundle = original_bundle.copy()

        # Assert that it's a different object
        assert copied_bundle is not original_bundle
