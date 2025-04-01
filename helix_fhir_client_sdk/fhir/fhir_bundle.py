import json
from typing import Any, Dict, List, Optional

from helix_fhir_client_sdk.fhir.fhir_bundle_entry_list import FhirBundleEntryList
from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource
from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder


class FhirBundle:
    __slots__ = ["entry", "total", "id_", "timestamp", "type_"]

    def __init__(
        self,
        *,
        id_: Optional[str] = None,
        timestamp: Optional[str] = None,
        type_: str,
        entry: Optional[FhirBundleEntryList] = None,
        total: Optional[int] = None,
    ) -> None:
        self.entry: Optional[FhirBundleEntryList] = entry
        self.total: Optional[int] = total
        self.id_: Optional[str] = id_
        self.timestamp: Optional[str] = timestamp
        self.type_: str = type_

    def to_dict(self) -> Dict[str, Any]:
        entries: List[Dict[str, Any]] | None = (
            [entry.to_dict() for entry in self.entry] if self.entry else None
        )
        result: Dict[str, Any] = {"type": self.type_, "resourceType": "Bundle"}

        if self.id_ is not None:
            result["id"] = self.id_
        if self.timestamp is not None:
            result["timestamp"] = self.timestamp
        if self.total is not None:
            result["total"] = self.total
        if entries:
            result["entry"] = entries
        return result

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
                        details: Dict[str, Any] = issue.get("details")
                        if details is None:
                            issue["details"] = {}
                            details = issue["details"]
                        coding: Optional[List[Dict[str, Any]]] = details.get("coding")
                        if coding is None:
                            details["coding"] = []
                            coding = details["coding"]
                        assert coding is not None
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
        """
        Creates a copy of the Bundle.

        :return: A new FhirBundle object with the same attributes
        """
        return FhirBundle(
            entry=self.entry.copy() if self.entry else None,
            total=self.total,
            id_=self.id_,
            timestamp=self.timestamp,
            type_=self.type_,
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
        return f"FhirBundle({', '.join(properties)})"
