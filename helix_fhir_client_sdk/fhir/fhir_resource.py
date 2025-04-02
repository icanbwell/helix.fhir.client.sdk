import copy
import json
from typing import Any, Optional, Dict, List

from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict import (
    CompressedDict,
)
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder


class FhirResource(CompressedDict[str, Any]):
    """
    FhirResource is a class that represents a FHIR resource.
    """

    __slots__ = CompressedDict.__slots__

    def __init__(
        self,
        initial_dict: Optional[Dict[str, Any]] = None,
        *,
        storage_mode: CompressedDictStorageMode = CompressedDictStorageMode.default(),
        properties_to_cache: Optional[List[str]] = None,
    ) -> None:
        super().__init__(
            initial_dict=initial_dict,
            storage_mode=storage_mode,
            properties_to_cache=properties_to_cache or ["resourceType", "id"],
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

    def __deepcopy__(self, memo: Dict[int, Any]) -> "FhirResource":
        """Create a copy of the resource."""
        return FhirResource(
            initial_dict=super().to_dict(),
            storage_mode=self._storage_mode,
        )

    def __repr__(self) -> str:
        """Custom string representation for debugging."""
        return f"FhirResource({self.resource_type}/{self.id})"

    def copy(self) -> "FhirResource":
        """
        Creates a copy of the BundleEntry object.

        :return: A new BundleEntry object with the same attributes.
        """
        return copy.deepcopy(self)

    def to_dict(self, *, remove_nulls: bool = True) -> Dict[str, Any]:
        """
        Converts the FhirResource object to a dictionary.

        :param remove_nulls: If True, removes None values from the dictionary.
        :return: A dictionary representation of the FhirResource object.
        """
        result: Dict[str, Any] = copy.deepcopy(super().to_dict())
        if remove_nulls:
            result = FhirResource.remove_none_values_from_dict(result)
        return result

    @staticmethod
    def remove_none_values_from_dict_or_list(
        item: Dict[str, Any],
    ) -> Dict[str, Any] | List[Dict[str, Any]]:
        if isinstance(item, list):
            return [FhirResource.remove_none_values_from_dict(i) for i in item]
        if not isinstance(item, dict):
            return item
        return {
            k: FhirResource.remove_none_values_from_dict(v)
            for k, v in item.items()
            if v is not None
        }

    @staticmethod
    def remove_none_values_from_dict(item: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(item, dict):
            return item
        return {
            k: FhirResource.remove_none_values_from_dict_or_list(v)
            for k, v in item.items()
            if v is not None
        }

    def remove_nulls(self) -> None:
        """
        Removes None values from the resource dictionary.
        """
        self.replace(value=self.to_dict(remove_nulls=True))
