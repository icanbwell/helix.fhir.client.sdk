import copy
import json
from typing import Any, Dict, List, Optional, cast, OrderedDict

from helix_fhir_client_sdk.fhir.fhir_bundle_entry import FhirBundleEntry
from helix_fhir_client_sdk.fhir.fhir_bundle_entry_list import FhirBundleEntryList
from helix_fhir_client_sdk.fhir.fhir_identifier import FhirIdentifier
from helix_fhir_client_sdk.fhir.fhir_link import FhirLink
from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder


class FhirBundle:
    """
    FhirBundle represents a FHIR Bundle resource.
    """

    __slots__ = ["entry", "total", "id_", "identifier", "timestamp", "type_", "link"]

    def __init__(
        self,
        *,
        id_: Optional[str] = None,
        identifier: Optional[FhirIdentifier] = None,
        timestamp: Optional[str] = None,
        type_: str,
        entry: Optional[FhirBundleEntryList] = None,
        total: Optional[int] = None,
        link: Optional[List[FhirLink]] = None,
    ) -> None:
        """
        Initializes a FhirBundle object.


        :param id_: The ID of the Bundle.
        :param identifier: The identifier of the Bundle.
        :param timestamp: The timestamp of the Bundle.
        :param type_: The type of the Bundle (e.g., "searchset").
        :param entry: The entries in the Bundle.
        :param total: The total number of entries in the Bundle.
        :param link: The links associated with the Bundle.
        """
        self.entry: Optional[FhirBundleEntryList] = entry
        self.total: Optional[int] = total
        self.id_: Optional[str] = id_
        self.identifier: Optional[FhirIdentifier] = identifier
        self.timestamp: Optional[str] = timestamp
        self.type_: str = type_
        self.link: Optional[List[FhirLink]] = link

    def to_dict(self) -> OrderedDict[str, Any]:
        entries: List[Dict[str, Any]] | None = (
            [entry.to_dict() for entry in self.entry] if self.entry else None
        )
        result: OrderedDict[str, Any] = OrderedDict[str, Any](
            {"type": self.type_, "resourceType": "Bundle"}
        )

        if self.id_ is not None:
            result["id"] = self.id_
        if self.identifier is not None:
            result["identifier"] = self.identifier.to_dict()
        if self.timestamp is not None:
            result["timestamp"] = self.timestamp
        if self.total is not None:
            result["total"] = self.total
        if entries:
            result["entry"] = entries
        if self.link:
            result["link"] = [link.to_dict() for link in self.link]
        return result

    @classmethod
    def from_dict(
        cls,
        data: OrderedDict[str, Any] | Dict[str, Any],
        storage_mode: CompressedDictStorageMode,
    ) -> "FhirBundle":
        """
        Creates a FhirBundle object from a dictionary.

        :param data: A dictionary containing the Bundle data.
        :param storage_mode: The storage mode for the Bundle.
        :return: A FhirBundle object.
        """
        bundle = cls(
            id_=data.get("id") if isinstance(data.get("id"), str) else None,
            identifier=(
                FhirIdentifier.from_dict(data["identifier"])
                if "identifier" in data
                else None
            ),
            timestamp=(
                data.get("timestamp")
                if isinstance(data.get("timestamp"), str)
                else None
            ),
            type_=(
                cast(str, data.get("type"))
                if isinstance(data.get("type"), str)
                else "collection"
            ),
            total=data.get("total") if isinstance(data.get("total"), int) else None,
            entry=(
                FhirBundleEntryList(
                    [
                        FhirBundleEntry.from_dict(entry, storage_mode=storage_mode)
                        for entry in data.get("entry", [])
                    ]
                )
                if "entry" in data
                else None
            ),
            link=[FhirLink.from_dict(link) for link in data.get("link", [])],
        )
        return bundle

    @staticmethod
    def add_diagnostics_to_operation_outcomes(
        *, resource: FhirResource, diagnostics_coding: List[Dict[str, Any]]
    ) -> FhirResource:
        """
        Adds diagnostic coding to OperationOutcome resources to identify which call resulted in that OperationOutcome
        being returned by the server


        :param resource: The resource to add the diagnostics to
        :param diagnostics_coding: The diagnostics coding to add
        :return: The resource with the diagnostics added
        """
        with resource.transaction():
            if resource.resource_type == "OperationOutcome":
                issues = resource.get("issue")
                if issues:
                    for issue in issues:
                        coding: List[Dict[str, Any]] = issue.setdefault(
                            "details", {}
                        ).setdefault("coding", [])
                        coding.extend(diagnostics_coding)
        return resource

    def to_json(self) -> str:
        """
        Converts the Bundle to a JSON string.

        :return: JSON string representation of the Bundle
        """
        bundle_dict = self.to_dict()
        return json.dumps(bundle_dict, cls=FhirJSONEncoder)

    def copy(self) -> "FhirBundle":
        return copy.deepcopy(self)

    def __deepcopy__(self, memo: Dict[int, Any]) -> "FhirBundle":
        """
        Creates a copy of the Bundle.

        :return: A new FhirBundle object with the same attributes
        """
        return FhirBundle(
            entry=copy.deepcopy(self.entry) if self.entry else None,
            total=self.total,
            id_=self.id_,
            identifier=copy.deepcopy(self.identifier) if self.identifier else None,
            timestamp=self.timestamp,
            type_=self.type_,
            link=[copy.deepcopy(link) for link in self.link] if self.link else None,
        )

    def __repr__(self) -> str:
        """
        Returns a string representation of the Bundle.

        :return: String representation of the Bundle
        """
        properties: List[str] = []
        if self.id_:
            properties.append(f"id_={self.id_}")
        if self.type_:
            properties.append(f"type_={self.type_}")
        if self.timestamp:
            properties.append(f"timestamp={self.timestamp}")
        if self.total:
            properties.append(f"total={self.total}")
        if self.entry:
            properties.append(f"entry={len(self.entry)}")
        if self.link:
            properties.append(f"link={len(self.link)}")

        return f"FhirBundle({', '.join(properties)})"
