from abc import abstractmethod
from typing import Dict, Any, Optional, List

from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)


class BaseFhirMergeResourceResponseEntry:
    @property
    @abstractmethod
    def id_(self) -> Optional[str]:
        """Abstract property for id_"""
        ...

    @property
    @abstractmethod
    def uuid(self) -> Optional[str]:
        """Abstract property for uuid"""
        ...

    @property
    @abstractmethod
    def resource_type(self) -> Optional[str]:
        """Abstract property for resource_type"""
        ...

    @property
    @abstractmethod
    def issue(self) -> Optional[List[Dict[str, Any]]]:
        """Abstract property for issue"""
        ...

    @property
    @abstractmethod
    def error(self) -> Optional[str]:
        """Abstract property for error"""
        ...

    @property
    @abstractmethod
    def status(self) -> Optional[int]:
        """Abstract property for status"""
        ...

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]: ...

    @classmethod
    @abstractmethod
    def from_dict(
        cls, data: Dict[str, Any], *, storage_mode: CompressedDictStorageMode
    ) -> "BaseFhirMergeResourceResponseEntry": ...

    @classmethod
    @abstractmethod
    def from_json(
        cls, data: str, *, storage_mode: CompressedDictStorageMode
    ) -> "List[BaseFhirMergeResourceResponseEntry]": ...

    # noinspection PyPep8Naming
    @property
    @abstractmethod
    def resourceType(self) -> Optional[str]: ...

    @property
    @abstractmethod
    def errored(self) -> bool: ...

    @property
    @abstractmethod
    def id(self) -> Optional[str]: ...
