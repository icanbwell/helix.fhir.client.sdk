from collections import UserDict
from collections.abc import KeysView, ValuesView, ItemsView
from contextlib import contextmanager
from typing import Dict, Optional, Literal, Iterator, cast, List

import msgpack
import zlib

from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_access_error import (
    CompressedDictAccessError,
)

CompressedDictStorageMode = Literal["raw", "msgpack", "compressed_msgpack"]


class CompressedDict[K, V](UserDict[K, V]):
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
        super().__init__()
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

        if storage_mode == "raw":
            # Store the initial dictionary directly
            self._working_dict = initial_dict

    @contextmanager
    def access_context(self) -> Iterator["CompressedDict[K, V]"]:
        """
        Context manager to safely access and modify the dictionary.

        Deserializes the dictionary before entering the context
        Serializes the dictionary after exiting the context

        Raises:
            CompressedDictAccessError: If methods are called outside the context
        """
        try:
            # Deserialize the dictionary before entering the context
            if self._storage_mode == "raw":
                # For raw mode, create a deep copy of the existing dictionary
                self._working_dict = self._raw_dict
            else:
                # For serialized modes, deserialize
                compressed = self._storage_mode == "compressed_msgpack"
                self._working_dict = (
                    self._deserialize_dict(self._serialized_dict, compressed)
                    if self._serialized_dict
                    else {}
                )

            # Yield the working dictionary
            yield self

        finally:
            # Serialize the dictionary after exiting the context
            if self._storage_mode == "raw":
                # Update raw dict
                self._raw_dict = self._working_dict or {}
            elif self._storage_mode == "msgpack":
                # Serialize without compression
                self._serialized_dict = self._serialize_dict(
                    self._working_dict or {}, compressed=False
                )
            elif self._storage_mode == "compressed_msgpack":
                # Serialize with compression
                self._serialized_dict = self._serialize_dict(
                    self._working_dict or {}, compressed=True
                )

            # Clear the working dictionary
            self._working_dict = None

    @staticmethod
    def _serialize_dict(dictionary: Dict[K, V], compressed: bool = False) -> bytes:
        """
        Serialize entire dictionary using MessagePack

        Args:
            dictionary: Dictionary to serialize
            compressed: Whether to apply compression

        Returns:
            Serialized bytes
        """
        # Serialize using MessagePack
        packed = msgpack.packb(
            dictionary,
            use_bin_type=True,  # Preserve string/bytes distinction
            use_single_float=True,  # More compact float representation
        )

        # Optional compression
        if compressed:
            packed = zlib.compress(packed, level=zlib.Z_BEST_COMPRESSION)

        return packed

    @staticmethod
    def _deserialize_dict(
        serialized_dict: bytes, compressed: bool = False
    ) -> Dict[K, V]:
        """
        Deserialize entire dictionary from MessagePack

        Args:
            serialized_dict: Serialized dictionary bytes
            compressed: Whether the dictionary was compressed

        Returns:
            Deserialized dictionary
        """
        assert serialized_dict is not None, "Serialized dictionary cannot be None"

        # Decompress if needed
        to_unpack = zlib.decompress(serialized_dict) if compressed else serialized_dict

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
        if self._storage_mode == "raw":
            return self._raw_dict

        # Deserialize based on storage mode
        compressed: bool = self._storage_mode == "compressed_msgpack"
        deserialized: Dict[K, V] = (
            self._deserialize_dict(self._serialized_dict, compressed)
            if self._serialized_dict
            else {}
        )

        # For non-raw modes, do not keep deserialized dict
        return deserialized

    def __getitem__(self, key: K) -> V:
        """
        Retrieve a value

        Args:
            key: Dictionary key

        Returns:
            Value associated with the key
        """

        result: V | None = self._cached_properties.get(key)
        if result is not None:
            return result

        if self._working_dict is None:
            raise CompressedDictAccessError(
                "Dictionary access is only allowed within an access_context() block. "
                "Use 'with compressed_dict.access_context() as d:' to access the dictionary."
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
                "Dictionary modification is only allowed within an access_context() block. "
                "Use 'with compressed_dict.access_context() as d:' to modify the dictionary."
            )

        current_dict: Dict[K, V]
        if self._storage_mode == "raw":
            # Direct storage for raw mode
            self._raw_dict[key] = value
            current_dict = self._raw_dict
        else:
            # For serialized modes, create a new dict
            current_dict = self._get_dict()
            current_dict[key] = value

        self._update_serialized_dict(current_dict)

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

        if self._storage_mode == "raw":
            self._raw_dict = current_dict
        elif self._storage_mode == "msgpack":
            self._serialized_dict = self._serialize_dict(current_dict, compressed=False)
        elif self._storage_mode == "compressed_msgpack":
            self._serialized_dict = self._serialize_dict(current_dict, compressed=True)

    def __delitem__(self, key: K) -> None:
        """
        Delete an item

        Args:
            key: Key to delete
        """
        if self._working_dict is None:
            raise CompressedDictAccessError(
                "Dictionary modification is only allowed within an access_context() block. "
                "Use 'with compressed_dict.access_context() as d:' to modify the dictionary."
            )
        if self._storage_mode == "raw":
            del self._raw_dict[key]
            self._update_serialized_dict(self._raw_dict)
        else:
            # For serialized modes, create a new dict
            current_dict = self._get_dict()
            del current_dict[key]

            self._update_serialized_dict(current_dict)

    def __contains__(self, key: object) -> bool:
        """
        Check if a key exists

        Args:
            key: Key to check

        Returns:
            Whether the key exists
        """
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
                "Dictionary modification is only allowed within an access_context() block. "
                "Use 'with compressed_dict.access_context() as d:' to modify the dictionary."
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
        return dict(self._get_dict())

    def __repr__(self) -> str:
        """
        String representation of the dictionary

        Returns:
            String representation
        """
        dict_contents = self._get_dict()
        return (
            f"CompressedDict(storage_mode='{self._storage_mode}', "
            f"items={dict_contents})"
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
        if self._storage_mode == "raw":
            self._raw_dict.clear()
        else:
            self._serialized_dict = None

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
