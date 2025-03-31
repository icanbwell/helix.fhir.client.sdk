import json

from helix_fhir_client_sdk.fhir.bundle import Bundle
from helix_fhir_client_sdk.fhir.bundle_entry import BundleEntry
from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)


class TestBundle:
    def test_init_minimal(self) -> None:
        """Test initialization with minimal parameters."""
        bundle = Bundle(type_="searchset")
        assert bundle.type_ == "searchset"
        assert bundle.entry is None
        assert bundle.total is None
        assert bundle.id_ is None
        assert bundle.timestamp is None

    def test_init_full(self) -> None:
        """Test initialization with all parameters."""
        entries = [
            BundleEntry(
                resource={"resourceType": "Patient"},
                request=None,
                response=None,
                storage_mode=CompressedDictStorageMode(),
            ),
            BundleEntry(
                resource={"resourceType": "Observation"},
                request=None,
                response=None,
                storage_mode=CompressedDictStorageMode(),
            ),
        ]
        bundle = Bundle(
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
        bundle = Bundle(type_="searchset")
        result = bundle.to_dict()
        assert result == {"type": "searchset", "resourceType": "Bundle"}

    def test_to_dict_full(self) -> None:
        """Test converting to dictionary with all parameters."""
        entries = [
            BundleEntry(
                resource={"resourceType": "Patient"},
                request=None,
                response=None,
                storage_mode=CompressedDictStorageMode(),
            ),
            BundleEntry(
                resource={"resourceType": "Observation"},
                request=None,
                response=None,
                storage_mode=CompressedDictStorageMode(),
            ),
        ]
        bundle = Bundle(
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
        entries = [
            BundleEntry(
                resource={"resourceType": "Patient"},
                request=None,
                response=None,
                storage_mode=CompressedDictStorageMode(),
            ),
            BundleEntry(
                resource={"resourceType": "Observation"},
                request=None,
                response=None,
                storage_mode=CompressedDictStorageMode(),
            ),
        ]
        bundle = Bundle(
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

        updated_resource = Bundle.add_diagnostics_to_operation_outcomes(
            resource=resource, diagnostics_coding=diagnostics_coding
        )

        with updated_resource.transaction():
            assert (
                updated_resource["issue"][0]["details"]["coding"] == diagnostics_coding
            )
