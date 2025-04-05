import dataclasses
import json
from typing import Optional, Any, Dict, List

from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource


@dataclasses.dataclass(slots=True)
class FhirMergeResponseEntry:
    created: Optional[bool] = None
    updated: Optional[bool] = None
    deleted: Optional[bool] = None
    id_: Optional[str] = None
    uuid: Optional[str] = None
    resource_type: Optional[str] = None
    source_assigning_authority: Optional[str] = None
    resource_version: Optional[str] = None
    message: Optional[str] = None
    issue: Optional[str | Any] = None
    error: Optional[str] = None
    token: Optional[str] = None
    resource: Optional[FhirResource] = None
    status: Optional[int] = 200

    def to_dict(self) -> Dict[str, Any]:
        return {
            "created": self.created,
            "updated": self.updated,
            "deleted": self.deleted,
            "id_": self.id_,
            "uuid": self.uuid,
            "resource_type": self.resource_type,
            "source_assigning_authority": self.source_assigning_authority,
            "resource_version": self.resource_version,
            "message": self.message,
            "issue": self.issue,
            "error": self.error,
            "token": self.token,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FhirMergeResponseEntry":
        return FhirMergeResponseEntry(
            created=data.get("created"),
            updated=data.get("updated"),
            deleted=data.get("deleted"),
            id_=data.get("id_"),
            uuid=data.get("uuid"),
            resource_type=data.get("resource_type"),
            source_assigning_authority=data.get("source_assigning_authority"),
            resource_version=data.get("resource_version"),
            message=data.get("message"),
            issue=data.get("issue"),
            error=data.get("error"),
            token=data.get("token"),
            resource=(
                FhirResource(data.get("resource")) if data.get("resource") else None
            ),
            status=data.get("status"),
        )

    @classmethod
    def from_issue_text(cls, issue_text: str) -> "FhirMergeResponseEntry":
        return FhirMergeResponseEntry.from_dict({"issue": issue_text})

    @classmethod
    def from_json(cls, data: str) -> "List[FhirMergeResponseEntry]":
        loaded_data: Dict[str, Any] | List[Dict[str, Any]] = json.loads(data)
        if isinstance(loaded_data, list):
            return [FhirMergeResponseEntry.from_dict(d) for d in loaded_data]
        else:
            return [FhirMergeResponseEntry.from_dict(loaded_data)]
