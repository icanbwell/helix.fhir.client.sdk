import dataclasses
from abc import ABC, abstractmethod
from typing import Any

from compressedfhir.fhir.fhir_resource import FhirResource
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)


@dataclasses.dataclass(kw_only=True, slots=True)
class BaseFhirMergeResourceResponseEntry(ABC):
    # Option 1: Fields with init=False and default=None
    id_: str | None = dataclasses.field(
        init=False,
        default=None,
        metadata={"description": "Unique identifier for the entry"},
    )

    uuid: str | None = dataclasses.field(
        init=False,
        default=None,
        metadata={"description": "Universally unique identifier"},
    )

    issue: list[dict[str, Any]] | None = dataclasses.field(
        init=False,
        default=None,
        metadata={"description": "List of issues associated with the entry"},
    )

    error: str | None = dataclasses.field(
        init=False,
        default=None,
        metadata={"description": "Error message for the entry"},
    )

    status: int | None = dataclasses.field(
        init=False, default=None, metadata={"description": "Status code for the entry"}
    )

    # Additional fields from the original implementation
    resource_type: str | None = dataclasses.field(
        init=False,
        default=None,
        metadata={"description": "Resource type (alternative naming)"},
    )

    resource: FhirResource | None = dataclasses.field(
        init=False, default=None, metadata={"description": "The actual FHIR resource"}
    )

    errored: bool = dataclasses.field(
        init=False,
        default=False,
        metadata={"description": "Flag indicating if the entry has an error"},
    )

    token: str | None = dataclasses.field(
        init=False,
        default=None,
        metadata={"description": "Authentication or access token"},
    )

    created: bool | None = dataclasses.field(
        init=False,
        default=None,
        metadata={"description": "Flag indicating if the resource was created"},
    )

    updated: bool | None = dataclasses.field(
        init=False,
        default=None,
        metadata={"description": "Flag indicating if the resource was updated"},
    )

    # Abstract methods remain the same
    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Convert the entry to a dictionary representation."""

    @classmethod
    @abstractmethod
    def from_dict(
        cls, data: dict[str, Any], *, storage_mode: CompressedDictStorageMode
    ) -> "BaseFhirMergeResourceResponseEntry":
        """Create an instance from a dictionary."""

    @classmethod
    @abstractmethod
    def from_json(
        cls, data: str, *, storage_mode: CompressedDictStorageMode
    ) -> "list[BaseFhirMergeResourceResponseEntry]":
        """Create instances from a JSON string."""

    def get_resource(self) -> FhirResource | None:
        """
        Get the resource from the entry.
        Added for backwards compatibility.

        :return: The FHIR resource.
        """
        return self.resource

    # noinspection PyPep8Naming
    @property
    def resourceType(self) -> str | None:
        """Get the resource type from the entry."""
        return self.resource_type

    # noinspection PyPep8Naming
    @resourceType.setter
    def resourceType(self, value: str | None) -> None:
        """Set the resource type for the entry."""
        self.resource_type = value

    @property
    def id(self) -> str | None:
        """Get the ID from the entry."""
        return self.id_

    @id.setter
    def id(self, value: str | None) -> None:
        """Set the ID for the entry."""
        self.id_ = value
