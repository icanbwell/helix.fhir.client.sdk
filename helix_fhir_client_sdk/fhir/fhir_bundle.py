import copy
import json
from typing import Any, Dict, List, Optional, cast, OrderedDict

from helix_fhir_client_sdk.fhir.fhir_bundle_entry import FhirBundleEntry
from helix_fhir_client_sdk.fhir.fhir_bundle_entry_list import FhirBundleEntryList
from helix_fhir_client_sdk.fhir.fhir_identifier import FhirIdentifier
from helix_fhir_client_sdk.fhir.fhir_link import FhirLink
from helix_fhir_client_sdk.fhir.fhir_meta import FhirMeta
from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder
from helix_fhir_client_sdk.utilities.json_helpers import FhirClientJsonHelpers


class FhirBundle:
    """
    FhirBundle represents a FHIR Bundle resource.
    """

    __slots__ = [
        "entry",
        "total",
        "id_",
        "identifier",
        "timestamp",
        "type_",
        "link",
        "meta",
    ]

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
        meta: Optional[FhirMeta] = None,
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
        :param meta: The metadata associated with the Bundle.
        """
        self.entry: FhirBundleEntryList = entry or FhirBundleEntryList()
        self.total: Optional[int] = total
        self.id_: Optional[str] = id_
        self.identifier: Optional[FhirIdentifier] = identifier
        self.timestamp: Optional[str] = timestamp
        self.type_: str = type_
        self.link: Optional[List[FhirLink]] = link
        self.meta: Optional[FhirMeta] = meta

    def dict(self) -> OrderedDict[str, Any]:
        entries: List[Dict[str, Any]] | None = (
            [entry.dict() for entry in self.entry] if self.entry else None
        )
        result: OrderedDict[str, Any] = OrderedDict[str, Any](
            {"type": self.type_, "resourceType": "Bundle"}
        )

        if self.id_ is not None:
            result["id"] = self.id_
        if self.identifier is not None:
            result["identifier"] = self.identifier.dict()
        if self.timestamp is not None:
            result["timestamp"] = self.timestamp
        if self.total is not None:
            result["total"] = self.total
        if entries and len(entries) > 0:
            result["entry"] = entries
        if self.link:
            result["link"] = [link.dict() for link in self.link]
        if self.meta:
            result["meta"] = self.meta.dict()
        return FhirClientJsonHelpers.remove_empty_elements_from_ordered_dict(result)

    @classmethod
    def construct(
        cls,
        *,
        id_: Optional[str] = None,
        identifier: Optional[FhirIdentifier] = None,
        timestamp: Optional[str] = None,
        type_: str,
        entry: Optional[FhirBundleEntryList] = None,
        total: Optional[int] = None,
        link: Optional[List[FhirLink]] = None,
        meta: Optional[FhirMeta] = None,
    ) -> "FhirBundle":
        """
        Constructs a FhirBundle object from keyword arguments.

        :param id_: The ID of the Bundle.
        :param identifier: The identifier of the Bundle.
        :param timestamp: The timestamp of the Bundle.
        :param type_: The type of the Bundle (e.g., "searchset").
        :param entry: The entries in the Bundle.
        :param total: The total number of entries in the Bundle.
        :param link: The links associated with the Bundle.
        :param meta: The metadata associated with the Bundle.
        """
        return cls(
            id_=id_,
            identifier=identifier,
            timestamp=timestamp,
            type_=type_,
            entry=entry,
            total=total,
            link=link,
            meta=meta,
        )

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
                else FhirBundleEntryList()
            ),
            link=[FhirLink.from_dict(link) for link in data.get("link", [])],
            meta=data.get("meta"),
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

    def json(self) -> str:
        """
        Converts the Bundle to a JSON string.

        :return: JSON string representation of the Bundle
        """
        bundle_dict = self.dict()
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

    def get_count_by_resource_type(self) -> Dict[str, int]:
        """
        Gets the count of resources by resource type.

        :return: The count of resources by resource type
        """
        resources_by_type: Dict[str, int] = dict()
        if self.entry is None:
            return resources_by_type

        entry: FhirBundleEntry
        for entry in [e for e in self.entry if e is not None]:
            if entry.resource is not None:
                resource = entry.resource
                resource_type: str = resource.resource_type or "unknown"
                if resource_type not in resources_by_type:
                    resources_by_type[resource_type] = 0
                resources_by_type[resource_type] += 1
        return resources_by_type

    @property
    def id(self) -> Optional[str]:
        """Get the ID of the Bundle."""
        return self.id_

    @id.setter
    def id(self, value: Optional[str]) -> None:
        """Set the ID of the Bundle."""
        self.id_ = value

    @property
    def resource_type(self) -> str:
        """Get the resource type of the Bundle."""
        return "Bundle"

    def to_plain_dict(self) -> Dict[str, Any]:
        """
        Converts the Bundle to a plain dictionary.

        :return: Plain dictionary representation of the Bundle
        """
        return cast(
            Dict[str, Any], json.loads(json.dumps(self.dict(), cls=FhirJSONEncoder))
        )
