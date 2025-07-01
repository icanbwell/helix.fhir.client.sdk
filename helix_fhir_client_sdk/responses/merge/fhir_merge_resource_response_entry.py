import dataclasses
import json
from typing import Any, override

from compressedfhir.fhir.fhir_resource import FhirResource
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)

from helix_fhir_client_sdk.responses.merge.base_fhir_merge_resource_response_entry import (
    BaseFhirMergeResourceResponseEntry,
)


@dataclasses.dataclass(kw_only=True, slots=True)
class FhirMergeResourceResponseEntry(BaseFhirMergeResourceResponseEntry):
    resource_type: str | None
    token: str | None
    resource: FhirResource | None
    status: int | None = 200
    created: bool | None = None
    updated: bool | None = None
    deleted: bool | None = None
    id_: str | None = None
    uuid: str | None = None
    source_assigning_authority: str | None = None
    resource_version: str | None = None
    message: str | None = None
    issue: list[dict[str, Any]] | None = None
    error: str | None = None

    @override
    def to_dict(self) -> dict[str, Any]:
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

    def get_created_updated(self) -> dict[str, Any]:
        return {
            "created": self.created,
            "updated": self.updated,
            "resourceType": self.resourceType,
        }

    @classmethod
    @override
    def from_dict(
        cls, data: dict[str, Any], *, storage_mode: CompressedDictStorageMode
    ) -> "FhirMergeResourceResponseEntry":
        return FhirMergeResourceResponseEntry(
            created=data.get("created"),
            updated=data.get("updated"),
            deleted=data.get("deleted"),
            id_=data.get("id"),
            uuid=data.get("uuid"),
            resource_type=data.get("resourceType"),
            source_assigning_authority=data.get("source_assigning_authority"),
            resource_version=data.get("resource_version"),
            message=data.get("message"),
            issue=data.get("issue"),
            error=data.get("error"),
            token=data.get("token"),
            resource=(FhirResource(data.get("resource"), storage_mode=storage_mode) if data.get("resource") else None),
            status=data.get("status"),
        )

    @classmethod
    @override
    def from_json(
        cls, data: str, *, storage_mode: CompressedDictStorageMode
    ) -> list[BaseFhirMergeResourceResponseEntry]:
        if not data:
            return []
        loaded_data: dict[str, Any] | list[dict[str, Any]] = json.loads(data)
        if isinstance(loaded_data, list):
            return [FhirMergeResourceResponseEntry.from_dict(d, storage_mode=storage_mode) for d in loaded_data]
        else:
            return [FhirMergeResourceResponseEntry.from_dict(loaded_data, storage_mode=storage_mode)]

    def __repr__(self) -> str:
        return f"FhirMergeResourceResponseEntry({self.resource_type}/{self.id_})"
