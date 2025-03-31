import json
from typing import Any, Dict, List, Optional

from helix_fhir_client_sdk.fhir.bundle_entry import BundleEntry
from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource
from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder


class Bundle:
    __slots__ = ["entry", "total", "id_", "timestamp", "type_"]

    def __init__(
        self,
        *,
        id_: Optional[str] = None,
        timestamp: Optional[str] = None,
        type_: str,
        entry: Optional[List[BundleEntry]] = None,
        total: Optional[int] = None,
    ) -> None:
        self.entry: Optional[List[BundleEntry]] = entry
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
            if resource.get("resourceType") == "OperationOutcome":
                if resource.get("issue"):
                    for issue in resource["issue"]:
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
