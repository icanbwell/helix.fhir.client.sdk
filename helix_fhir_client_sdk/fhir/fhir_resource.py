import copy
import json
from typing import Any, Optional, Dict, List, cast, OrderedDict, override

from helix_fhir_client_sdk.fhir.fhir_meta import FhirMeta
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict import (
    CompressedDict,
)
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder
from helix_fhir_client_sdk.utilities.json_helpers import FhirClientJsonHelpers


class FhirResource(CompressedDict[str, Any]):
    """
    FhirResource is a class that represents a FHIR resource.
    """

    __slots__ = CompressedDict.__slots__

    def __init__(
        self,
        initial_dict: Dict[str, Any] | OrderedDict[str, Any] | None = None,
        *,
        meta: Optional[FhirMeta] = None,
        storage_mode: CompressedDictStorageMode = CompressedDictStorageMode.default(),
        properties_to_cache: Optional[List[str]] = None,
    ) -> None:
        if meta is not None:
            initial_dict = initial_dict or {}
            initial_dict["meta"] = meta.dict()
        super().__init__(
            initial_dict=initial_dict,
            storage_mode=storage_mode,
            properties_to_cache=properties_to_cache or ["resourceType", "id", "meta"],
        )

    @classmethod
    def construct(cls, **kwargs: Any) -> "FhirResource":
        """
        Constructs a FhirResource object from keyword arguments.

        :param kwargs: Keyword arguments to initialize the resource.
        :return: A FhirResource object.
        """
        return cls(initial_dict=kwargs)

    @property
    def resource_type(self) -> Optional[str]:
        """Get the resource type from the resource dictionary."""
        return self.get("resourceType")

    @property
    def resource_type_and_id(self) -> Optional[str]:
        """Get the resource type and ID from the resource dictionary."""
        return (
            f"{self.resource_type}/{self.id}"
            if self.resource_type and self.id
            else None
        )

    def json(self) -> str:
        """Convert the resource to a JSON string."""
        return json.dumps(obj=self.dict(), cls=FhirJSONEncoder)

    @classmethod
    def from_json(cls, json_str: str) -> "FhirResource":
        """
        Create a FhirResource object from a JSON string.

        :param json_str: The JSON string to convert.
        :return: A FhirResource object.
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    def __deepcopy__(self, memo: Dict[int, Any]) -> "FhirResource":
        """Create a copy of the resource."""
        return FhirResource(
            initial_dict=super().dict(),
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

    @override
    def dict(self, *, remove_nulls: bool = True) -> OrderedDict[str, Any]:
        """
        Converts the FhirResource object to a dictionary.

        :param remove_nulls: If True, removes None values from the dictionary.
        :return: A dictionary representation of the FhirResource object.
        """
        ordered_dict = super().dict()
        result: OrderedDict[str, Any] = copy.deepcopy(ordered_dict)
        if remove_nulls:
            result = cast(
                OrderedDict[str, Any],
                FhirClientJsonHelpers.remove_empty_elements_from_ordered_dict(result),
            )
        return result

    @classmethod
    def from_dict(
        cls,
        d: Dict[str, Any],
        *,
        storage_mode: CompressedDictStorageMode = CompressedDictStorageMode.default(),
    ) -> "FhirResource":
        """
        Creates a FhirResource object from a dictionary.

        :param d: The dictionary to convert.
        :param storage_mode: The storage mode for the CompressedDict.
        :return: A FhirResource object.
        """
        return cls(initial_dict=d, storage_mode=storage_mode)

    def remove_nulls(self) -> None:
        """
        Removes None values from the resource dictionary.
        """
        self.replace(value=self.dict(remove_nulls=True))

    @property
    def id(self) -> Optional[str]:
        """Get the ID from the resource dictionary."""
        return self.get("id")

    @id.setter
    def id(self, value: Optional[str]) -> None:
        """Set the ID of the Bundle."""
        self["id"] = value

    @property
    def meta(self) -> FhirMeta | None:
        """Get the meta information from the resource dictionary."""
        return (
            FhirMeta.from_dict(cast(Dict[str, Any], self.get("meta")))
            if "meta" in self
            else None
        )

    @meta.setter
    def meta(self, value: FhirMeta | None) -> None:
        """Set the meta information of the resource."""
        if value is None:
            self.pop("meta", None)
        else:
            assert isinstance(value, FhirMeta)
            self["meta"] = value.dict()
