import dataclasses
import json
from typing import Optional, Any, Dict, List, override

from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource
from helix_fhir_client_sdk.responses.merge.base_fhir_merge_resource_response_entry import (
    BaseFhirMergeResourceResponseEntry,
)
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)


@dataclasses.dataclass(slots=True)
class FhirMergeResponseEntryError(BaseFhirMergeResourceResponseEntry):
    status: Optional[int]
    issue: Optional[List[Dict[str, Any]]]
    error: Optional[str]
    token: Optional[str]
    resource_type: Optional[str]
    id_: Optional[str] = None
    uuid: Optional[str] = None

    @override
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id_": self.id_,
            "uuid": self.uuid,
            "resource_type": self.resource_type,
            "issue": self.issue,
            "error": self.error,
        }

    @classmethod
    def from_dict(
        cls, data: Dict[str, Any], *, storage_mode: CompressedDictStorageMode
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
    ) -> List[BaseFhirMergeResourceResponseEntry]:
        if not data:
            return []
        loaded_data: Dict[str, Any] | List[Dict[str, Any]] = json.loads(data)
        if isinstance(loaded_data, list):
            return [
                FhirMergeResponseEntryError.from_dict(d, storage_mode=storage_mode)
                for d in loaded_data
            ]
        else:
            return [
                FhirMergeResponseEntryError.from_dict(
                    loaded_data, storage_mode=storage_mode
                )
            ]

    # noinspection PyPep8Naming
    @property
    def resourceType(self) -> Optional[str]:
        return self.resource_type

    @resourceType.setter
    def resourceType(self, value: str) -> None:
        self.resource_type = value

    @property
    def errored(self) -> bool:
        return True

    @property
    @override
    def id(self) -> Optional[str]:
        """Get the ID of the Bundle."""
        return self.id_

    @id.setter
    def id(self, value: str) -> None:
        """Set the ID of the Bundle."""
        self.id_ = value

    @property
    @override
    def resource(self) -> Optional[FhirResource]:
        raise NotImplementedError(
            "This method is not implemented for FhirMergeResponseEntryError."
        )

    @resource.setter
    def resource(self, value: FhirResource) -> None:
        raise NotImplementedError(
            "This method is not implemented for FhirMergeResponseEntryError."
        )

    @property
    @override
    def created(self) -> Optional[bool]:
        return False

    @property
    @override
    def updated(self) -> Optional[bool]:
        return False
