import dataclasses
import json
from typing import Any, override

from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)

from helix_fhir_client_sdk.responses.merge.base_fhir_merge_resource_response_entry import (
    BaseFhirMergeResourceResponseEntry,
)


@dataclasses.dataclass(kw_only=True, slots=True)
class FhirMergeResponseEntryError(BaseFhirMergeResourceResponseEntry):
    status: int | None
    issue: list[dict[str, Any]] | None
    error: str | None
    token: str | None
    resource_type: str | None
    id_: str | None = None
    uuid: str | None = None

    @override
    def to_dict(self) -> dict[str, Any]:
        return {
            "id_": self.id_,
            "uuid": self.uuid,
            "resource_type": self.resource_type,
            "issue": self.issue,
            "error": self.error,
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], *, storage_mode: CompressedDictStorageMode
    ) -> "FhirMergeResponseEntryError":
        return FhirMergeResponseEntryError(
            id_=data.get("id"),
            uuid=data.get("uuid"),
            resource_type=data.get("resourceType"),
            issue=data.get("issue"),
            error=data.get("error"),
            status=data.get("status"),
            token=data.get("token"),
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
            return [FhirMergeResponseEntryError.from_dict(d, storage_mode=storage_mode) for d in loaded_data]
        else:
            return [FhirMergeResponseEntryError.from_dict(loaded_data, storage_mode=storage_mode)]

    def _repr__(self) -> str:
        return f"FhirMergeResponseEntryError({self.resource_type}/{self.id_}: {self.error})"
