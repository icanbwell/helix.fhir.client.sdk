import dataclasses
from typing import Optional, Any, Dict


@dataclasses.dataclass(slots=True)
class FhirMergeResponseEntryError:
    id_: Optional[str] = None
    uuid: Optional[str] = None
    resource_type: Optional[str] = None
    issue: Optional[str | Any] = None
    error: Optional[str] = None
    status: Optional[int] = 200

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id_": self.id_,
            "uuid": self.uuid,
            "resource_type": self.resource_type,
            "issue": self.issue,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FhirMergeResponseEntryError":
        return FhirMergeResponseEntryError(
            id_=data.get("id_"),
            uuid=data.get("uuid"),
            resource_type=data.get("resource_type"),
            issue=data.get("issue"),
            error=data.get("error"),
            status=data.get("status"),
        )
