import dataclasses
from typing import Any, Dict


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

    def dict(self) -> Dict[str, Any]:
        return {
            "versionId": self.version_id,
            "lastUpdated": self.last_updated,
            "source": self.source,
            "profile": self.profile,
            "security": self.security,
            "tag": self.tag,
        }

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
