import dataclasses
from typing import Any, Dict, OrderedDict

from helix_fhir_client_sdk.utilities.json_helpers import FhirClientJsonHelpers


@dataclasses.dataclass(slots=True)
class FhirMeta:
    """
    FhirMeta represents the meta information of a FHIR resource.
    """

    version_id: str | None = None
    last_updated: str | None = None
    source: str | None = None
    profile: list[str] | None = None
    security: list[Dict[str, Any]] | None = None
    tag: list[str] | None = None

    def dict(self) -> OrderedDict[str, Any]:
        result: OrderedDict[str, Any] = OrderedDict[str, Any]()
        if self.version_id is not None:
            result["versionId"] = self.version_id
        if self.last_updated is not None:
            result["lastUpdated"] = self.last_updated
        if self.source is not None:
            result["source"] = self.source
        if self.profile is not None:
            result["profile"] = [p for p in self.profile if p]
        if self.security is not None:
            result["security"] = [
                FhirClientJsonHelpers.remove_empty_elements(s) for s in self.security
            ]
        if self.tag is not None:
            result["tag"] = [t for t in self.tag if t]
        return FhirClientJsonHelpers.remove_empty_elements_from_ordered_dict(result)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FhirMeta":
        return cls(
            version_id=data.get("versionId"),
            last_updated=data.get("lastUpdated"),
            source=data.get("source"),
            profile=data.get("profile"),
            security=data.get("security"),
            tag=data.get("tag"),
        )
