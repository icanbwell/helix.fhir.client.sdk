import json
from collections.abc import KeysView, ValuesView, ItemsView
from contextlib import contextmanager
from typing import Dict, Optional, Iterator, cast, List, overload

import msgpack
import zlib

from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_access_error import (
    CompressedDictAccessError,
)
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
    CompressedDictStorageType,
)
from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder


class CompressedDict[K, V]:
    # use slots to reduce memory usage
    __slots__ = (
        "_storage_mode",
        "_working_dict",
        "_raw_dict",
        "_serialized_dict",
        "_properties_to_cache",
        "_cached_properties",
        "_length",
    )

    def __init__(
        self,
        *,
        initial_dict: Optional[Dict[K, V]] = None,
        storage_mode: CompressedDictStorageMode,
        properties_to_cache: List[K] | None,
    ) -> None:
        """
        Initialize a dictionary with flexible storage options
        Args:
            initial_dict: Initial dictionary to store
            storage_mode: Storage method for dictionary contents
                - 'raw': Store as original dictionary
                - 'msgpack': Store as MessagePack serialized bytes
                - 'compressed_msgpack': Store as compressed MessagePack bytes
        """
        # Storage configuration
        self._storage_mode: CompressedDictStorageMode = storage_mode

        # Working copy of the dictionary during context
        self._working_dict: Optional[Dict[K, V]] = None

        # Private storage options
        self._raw_dict: Dict[K, V] = {}
        self._serialized_dict: Optional[bytes] = None

        self._properties_to_cache: List[K] | None = properties_to_cache

        self._cached_properties: Dict[K, V] = {}

        self._length: int = 0

        # Populate initial dictionary if provided
        if initial_dict:
            self.replace(value=initial_dict)

        if storage_mode.storage_type == "raw":
            # Store the initial dictionary directly
            self._working_dict = initial_dict

    @contextmanager
    def transaction(self) -> Iterator["CompressedDict[K, V]"]:
        """
        Context manager to safely access and modify the dictionary.

        Deserializes the dictionary before entering the context
        Serializes the dictionary after exiting the context

        Raises:
            CompressedDictAccessError: If methods are called outside the context
        """
        try:
            self.ensure_working_dict()

            # Yield the working dictionary
            yield self

        finally:
            self._update_serialized_dict(current_dict=self._working_dict)

            # Clear the working dictionary
            self._working_dict = None

    def ensure_working_dict(self) -> None:
        """
        Ensures that the working dictionary is initialized and deserialized.

        """
        if not self._working_dict:
            self._working_dict = self.create_working_dict()

    def create_working_dict(self) -> Dict[K, V]:
        working_dict: Dict[K, V]
        # Deserialize the dictionary before entering the context
        if self._storage_mode.storage_type == "raw":
            # For raw mode, create a deep copy of the existing dictionary
            working_dict = self._raw_dict
        else:
            # For serialized modes, deserialize
            working_dict = (
                self._deserialize_dict(
                    serialized_dict=self._serialized_dict,
                    storage_type=self._storage_mode.storage_type,
                )
                if self._serialized_dict
                else {}
            )
        return working_dict

    @staticmethod
    def _serialize_dict(
        *, dictionary: Dict[K, V], storage_type: CompressedDictStorageType
    ) -> bytes:
        """
        Serialize entire dictionary using MessagePack

        Args:
            dictionary: Dictionary to serialize
            storage_type: Storage type to use for serialization

        Returns:
            Serialized bytes
        """
        if storage_type == "compressed":
            # Serialize to JSON and compress with zlib
            json_str = json.dumps(
                dictionary, separators=(",", ":"), cls=FhirJSONEncoder
            )  # Most compact JSON representation
            return zlib.compress(
                json_str.encode("utf-8"), level=zlib.Z_BEST_COMPRESSION
            )

        # Serialize using MessagePack
        packed = msgpack.packb(
            dictionary,
            use_bin_type=True,  # Preserve string/bytes distinction
            use_single_float=True,  # More compact float representation
        )

        # Optional compression
        if storage_type == "compressed_msgpack":
            packed = zlib.compress(packed, level=zlib.Z_BEST_COMPRESSION)

        return packed

    @staticmethod
    def _deserialize_dict(
        *,
        serialized_dict: bytes,
        storage_type: CompressedDictStorageType,
    ) -> Dict[K, V]:
        """
        Deserialize entire dictionary from MessagePack

        Args:
            serialized_dict: Serialized dictionary bytes

        Returns:
            Deserialized dictionary
        """
        assert serialized_dict is not None, "Serialized dictionary cannot be None"

        if storage_type == "compressed":
            # Decompress and parse JSON
            decompressed = zlib.decompress(serialized_dict)
            return cast(Dict[K, V], json.loads(decompressed.decode("utf-8")))

        # Decompress if needed
        to_unpack = (
            zlib.decompress(serialized_dict)
            if storage_type == "compressed_msgpack"
            else serialized_dict
        )

        # Deserialize
        return cast(
            Dict[K, V],
            msgpack.unpackb(
                to_unpack,
                raw=False,  # Convert to strings
                strict_map_key=False,  # Handle potential key type variations
            ),
        )

    def _get_dict(self) -> Dict[K, V]:
        """
        Get the dictionary, deserializing if necessary

        Returns:
            Current dictionary state
        """

        if self._working_dict is None:
            raise CompressedDictAccessError(
                "Dictionary access is only allowed within an transaction() block. "
                "Use 'with compressed_dict.transaction() as d:' to access the dictionary."
                f"You tried to access it with storage type {self._storage_mode.storage_type}."
            )

        if self._storage_mode.storage_type == "raw":
            return self._raw_dict

        # For non-raw modes, do not keep deserialized dict
        return self._working_dict

    def __getitem__(self, key: K) -> V:
        """
        Retrieve a value

        Args:
            key: Dictionary key

        Returns:
            Value associated with the key
        """

        if self._properties_to_cache and key in self._properties_to_cache:
            return self._cached_properties[key]

        if self._working_dict is None:
            raise CompressedDictAccessError(
                "Dictionary access is only allowed within an transaction() block. "
                "Use 'with compressed_dict.transaction() as d:' to access the dictionary."
            )
        return self._get_dict()[key]

    def __setitem__(self, key: K, value: V) -> None:
        """
        Set a value

        Args:
            key: Dictionary key
            value: Value to store
        """
        if self._working_dict is None:
            raise CompressedDictAccessError(
                "Dictionary modification is only allowed within an transaction() block. "
                "Use 'with compressed_dict.transaction() as d:' to modify the dictionary."
            )

        # Update the working dictionary
        self._working_dict[key] = value

    def _update_serialized_dict(self, current_dict: Dict[K, V] | None) -> None:
        if current_dict is None:
            self._cached_properties.clear()
            self._length = 0
            self._serialized_dict = None
            self._raw_dict = {}
            return

        if self._properties_to_cache:
            for key in self._properties_to_cache:
                if key in current_dict:
                    self._cached_properties[key] = current_dict[key]

        self._length = len(current_dict)

        if self._storage_mode.storage_type == "raw":
            self._raw_dict = current_dict
        else:
            self._serialized_dict = (
                self._serialize_dict(
                    dictionary=current_dict,
                    storage_type=self._storage_mode.storage_type,
                )
                if current_dict
                else None
            )

    def __delitem__(self, key: K) -> None:
        """
        Delete an item

        Args:
            key: Key to delete
        """
        if self._working_dict is None:
            raise CompressedDictAccessError(
                "Dictionary modification is only allowed within an transaction() block. "
                "Use 'with compressed_dict.transaction() as d:' to modify the dictionary."
            )

        del self._working_dict[key]

    def __contains__(self, key: object) -> bool:
        """
        Check if a key exists

        Args:
            key: Key to check

        Returns:
            Whether the key exists
        """
        # first check if the key is in the cached properties
        if self._properties_to_cache and key in self._properties_to_cache:
            return self._cached_properties.__contains__(key)

        return self._get_dict().__contains__(key)

    def __len__(self) -> int:
        """
        Get the number of items

        Returns:
            Number of items in the dictionary
        """
        return self._length

    def __iter__(self) -> Iterator[K]:
        """
        Iterate over keys

        Returns:
            Iterator of keys
        """
        if self._working_dict is None:
            raise CompressedDictAccessError(
                "Dictionary modification is only allowed within an transaction() block. "
                "Use 'with compressed_dict.transaction() as d:' to modify the dictionary."
            )
        return iter(self._get_dict())

    def keys(self) -> KeysView[K]:
        """
        Get an iterator of keys

        Returns:
            Iterator of keys
        """
        return self._get_dict().keys()

    def values(self) -> ValuesView[V]:
        """
        Get an iterator of values

        Returns:
            Iterator of values
        """
        return self._get_dict().values()

    def items(self) -> ItemsView[K, V]:
        """
        Get an iterator of key-value pairs

        Returns:
            Iterator of key-value pairs
        """
        return self._get_dict().items()

    def to_dict(self) -> Dict[K, V]:
        """
        Convert to a standard dictionary

        Returns:
            Standard dictionary with all values
        """
        if self._working_dict:
            return self._working_dict
        else:
            # if the working dict is None, return it but don't store it in the self._working_dict to keep memory low
            return self.create_working_dict()

    def __repr__(self) -> str:
        """
        String representation of the dictionary

        Returns:
            String representation
        """
        return (
            f"CompressedDict(storage_type='{self._storage_mode.storage_type}', "
            f"items={self._length})"
        )

    def replace(self, *, value: Dict[K, V]) -> "CompressedDict[K, V]":
        """
        Replace the current dictionary with a new one

        Args:
            value: New dictionary to store

        Returns:
            Self
        """
        if not value:
            self.clear()
            return self

        self._update_serialized_dict(current_dict=value)
        return self

    def clear(self) -> None:
        """
        Clear the dictionary
        """
        self._update_serialized_dict(current_dict=None)

    def __eq__(self, other: object) -> bool:
        """
        Check equality with another dictionary

        Args:
            other: Dictionary to compare with

        Returns:
            Whether the dictionaries are equal
        """
        if isinstance(other, CompressedDict):
            return self._get_dict() == other._get_dict()
        return self._get_dict() == other

    @overload
    def get(self, key: K) -> Optional[V]:
        """
        Get a value
        """
        ...

    @overload
    def get(self, key: K, default: V) -> V:
        """
        Get a value with a default

        Args:
            key: Key to retrieve
            default: Default value if key is not found

        Returns:
            Value associated with the key or default
        """
        ...

    def get(self, key: K, default: Optional[V] = None) -> V | None:
        if key in self:
            return self[key]
        return default
