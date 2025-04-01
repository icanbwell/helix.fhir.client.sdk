import json
from typing import Any, Optional, Dict

from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict import (
    CompressedDict,
)
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder


class FhirResource(CompressedDict[str, Any]):
    __slots__ = CompressedDict.__slots__

    def __init__(
        self,
        initial_dict: Optional[Dict[str, Any]] = None,
        *,
        storage_mode: CompressedDictStorageMode,
    ) -> None:
        super().__init__(
            initial_dict=initial_dict,
            storage_mode=storage_mode,
            properties_to_cache=["resourceType", "id"],
        )

    @property
    def resource_type(self) -> Optional[str]:
        """Get the resource type from the resource dictionary."""
        return self.get("resourceType")

    @property
    def id(self) -> Optional[str]:
        """Get the ID from the resource dictionary."""
        return self.get("id")

    @property
    def resource_type_and_id(self) -> Optional[str]:
        """Get the resource type and ID from the resource dictionary."""
        return (
            f"{self.resource_type}/{self.id}"
            if self.resource_type and self.id
            else None
        )

    def __eq__(self, other: object) -> bool:
        """Check equality based on resource type and ID."""
        if not isinstance(other, FhirResource):
            return False
        return self.resource_type == other.resource_type and self.id == other.id

    def to_json(self) -> str:
        """Convert the resource to a JSON string."""
        return json.dumps(obj=self, cls=FhirJSONEncoder)

    def copy(self) -> "FhirResource":
        """Create a copy of the resource."""
        return FhirResource(
            initial_dict=self.to_dict(),
            storage_mode=self._storage_mode,
        )
