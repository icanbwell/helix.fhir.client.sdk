import copy
import json
from collections.abc import KeysView, ValuesView, ItemsView, MutableMapping
from contextlib import contextmanager
from typing import Dict, Optional, Iterator, cast, List, Any, overload, OrderedDict

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


class CompressedDict[K, V](MutableMapping[K, V]):
    """
    A dictionary-like class that supports flexible storage options.

    It can store data in raw format, MessagePack format, or compressed MessagePack format.
    """

    # use slots to reduce memory usage
    __slots__ = (
        "_storage_mode",
        "_working_dict",
        "_raw_dict",
        "_serialized_dict",
        "_properties_to_cache",
        "_cached_properties",
        "_length",
        "_transaction_depth",
    )

    def __init__(
        self,
        *,
        initial_dict: Dict[K, V] | OrderedDict[K, V] | None = None,
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
        self._working_dict: Optional[OrderedDict[K, V]] = None

        # Private storage options
        self._raw_dict: OrderedDict[K, V] = OrderedDict[K, V]()
        self._serialized_dict: Optional[bytes] = None

        self._properties_to_cache: List[K] | None = properties_to_cache

        self._cached_properties: Dict[K, V] = {}

        self._length: int = 0

        self._transaction_depth: int = 0

        # Populate initial dictionary if provided
        if initial_dict:
            # Ensure we use an OrderedDict to maintain original order
            initial_dict_ordered = (
                initial_dict
                if isinstance(initial_dict, OrderedDict)
                else OrderedDict[K, V](initial_dict)
            )
            self.replace(value=initial_dict_ordered)

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
            self.start_transaction()

            # Yield the working dictionary
            yield self

        finally:
            self.end_transaction()

    def start_transaction(self) -> "CompressedDict[K, V]":
        """
        Starts a transaction.  Use transaction() for a contextmanager for simpler usage.
        """
        # Increment transaction depth
        self._transaction_depth += 1
        # Ensure working dictionary is ready on first entry
        if self._transaction_depth == 1:
            self.ensure_working_dict()

        return self

    def end_transaction(self) -> "CompressedDict[K, V]":
        """
        Ends a transaction.  Use transaction() for a context_manager for simpler usage.

        """
        # Decrement transaction depth
        self._transaction_depth -= 1
        # Only update serialized dict when outermost transaction completes
        if self._transaction_depth == 0:
            self._update_serialized_dict(current_dict=self._working_dict)

            # Clear the working dictionary
            self._working_dict = None

        return self

    def ensure_working_dict(self) -> None:
        """
        Ensures that the working dictionary is initialized and deserialized.

        """
        if not self._working_dict:
            self._working_dict = self.create_working_dict()

    def create_working_dict(self) -> OrderedDict[K, V]:
        working_dict: OrderedDict[K, V]
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
                else OrderedDict[K, V]()
            )
            assert isinstance(working_dict, OrderedDict)
        return working_dict

    @staticmethod
    def _serialize_dict(
        *, dictionary: OrderedDict[K, V], storage_type: CompressedDictStorageType
    ) -> bytes:
        """
        Serialize entire dictionary using MessagePack

        Args:
            dictionary: Dictionary to serialize
            storage_type: Storage type to use for serialization

        Returns:
            Serialized bytes
        """
        assert isinstance(dictionary, OrderedDict)
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
    ) -> OrderedDict[K, V]:
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
            decoded_text = decompressed.decode("utf-8")
            # noinspection PyTypeChecker
            decompressed_dict = json.loads(decoded_text, object_pairs_hook=OrderedDict)
            assert isinstance(decompressed_dict, OrderedDict)
            return cast(OrderedDict[K, V], decompressed_dict)

        # Decompress if needed
        to_unpack = (
            zlib.decompress(serialized_dict)
            if storage_type == "compressed_msgpack"
            else serialized_dict
        )

        # Deserialize
        unpacked_dict = msgpack.unpackb(
            to_unpack,
            raw=False,  # Convert to strings
            strict_map_key=False,  # Handle potential key type variations
        )
        unpacked_dict = (
            unpacked_dict
            if isinstance(unpacked_dict, OrderedDict)
            else OrderedDict[K, V](unpacked_dict)
        )
        assert isinstance(unpacked_dict, OrderedDict)
        return cast(
            OrderedDict[K, V],
            unpacked_dict,
        )

    def _get_dict(self) -> OrderedDict[K, V]:
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

    def _update_serialized_dict(self, current_dict: OrderedDict[K, V] | None) -> None:
        if current_dict is None:
            self._cached_properties.clear()
            self._length = 0
            self._serialized_dict = None
            self._raw_dict = OrderedDict[K, V]()
            return

        if self._properties_to_cache:
            for key in self._properties_to_cache:
                if key in current_dict:
                    self._cached_properties[key] = current_dict[key]

        self._length = len(current_dict)

        if self._working_dict is not None:
            # If the working dictionary is None, initialize it
            self._working_dict = current_dict

        if self._transaction_depth == 0:
            # If we're in a transaction,
            # The serialized dictionary will be updated after the transaction
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

    def to_dict(self, *, remove_nulls: bool = True) -> OrderedDict[K, V]:
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
        cached_property_list: List[str] = [
            f"{k}={v}" for k, v in self._cached_properties.items()
        ]
        return (
            (
                f"CompressedDict(storage_type='{self._storage_mode.storage_type}', keys={self._length}"
            )
            + (", " if cached_property_list else "")
            + ", ".join(cached_property_list)
            + ")"
        )

    def replace(
        self, *, value: Dict[K, V] | OrderedDict[K, V]
    ) -> "CompressedDict[K, V]":
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

        new_dict: OrderedDict[K, V] = (
            value if isinstance(value, OrderedDict) else OrderedDict[K, V](value)
        )
        self._update_serialized_dict(current_dict=new_dict)
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
            other: Dictionary to compare with (CompressedDict or plain dict)

        Returns:
            Whether the dictionaries are equal in keys and values
        """
        # If other is not a dictionary-like object, return False
        if not isinstance(other, (CompressedDict, dict, OrderedDict)):
            return False

        # Get the dictionary representation of self
        self_dict = self.to_dict()

        # If other is a CompressedDict, use its _get_dict() method
        if isinstance(other, CompressedDict):
            other_dict = other.to_dict()
        else:
            # If other is a plain dict, use it directly
            if isinstance(other, OrderedDict):
                # If other is an OrderedDict, use it directly
                other_dict = other
            else:
                other_dict = OrderedDict[K, V](other)

        # Compare keys and values
        # Check that all keys in both dictionaries match exactly
        return set(self_dict.keys()) == set(other_dict.keys()) and all(
            self_dict[key] == other_dict[key] for key in self_dict
        )

    @overload
    def get(self, key: K) -> Optional[V]:
        """
        Get a value for an existing key

        :param key: Key to retrieve
        :return: Value or None if key is not found
        """
        ...

    # noinspection PyMethodOverriding
    @overload
    def get[_T](self, key: K, /, default: V | _T) -> V | _T:
        """
        Get a value with a default

        Args:
            key: Key to retrieve
            default: Default value if key is not found

        Returns:
            Value associated with the key or default
        """
        ...

    def get[_T](self, key: K, default: V | _T | None = None) -> V | _T | None:
        if key in self:
            return self[key]
        return default

    def __deepcopy__(self, memo: Dict[int, Any]) -> "CompressedDict[K, V]":
        """
        Create a deep copy of the dictionary

        Args:
            memo: Memoization dictionary for deep copy

        Returns:
            Deep copy of the dictionary
        """
        # Create a new instance with the same storage mode
        new_instance = CompressedDict(
            initial_dict=copy.deepcopy(self.to_dict()),
            storage_mode=self._storage_mode,
            properties_to_cache=self._properties_to_cache,
        )
        return new_instance

    def copy(self) -> "CompressedDict[K,V]":
        """
        Creates a copy of the BundleEntry object.

        :return: A new BundleEntry object with the same attributes.
        """
        return copy.deepcopy(self)

    def get_storage_mode(self) -> CompressedDictStorageMode:
        """
        Get the storage mode

        Returns:
            Storage mode
        """
        return self._storage_mode

    @overload
    def pop(self, key: K, /) -> V:
        """
        Remove and return a value for an existing key

        :param key: Key to remove
        :return: Removed value
        :raises KeyError: If key is not found
        """
        ...

    # noinspection PyMethodOverriding
    @overload
    def pop[_T](self, key: K, /, default: _T) -> V | _T:
        """
        Remove and return a value, or return default if key is not found

        :param key: Key to remove
        :param default: Default value to return if key is not found
        :return: Removed value or default
        """
        ...

    def pop[_T](self, key: K, /, default: V | _T | None = None) -> V | _T | None:
        """
        Remove and return a value

        :param key: Key to remove
        :param default: Optional default value if key is not found
        :return: Removed value or default
        :raises KeyError: If key is not found and no default is provided
        """
        if self._working_dict is None:
            raise CompressedDictAccessError(
                "Dictionary modification is only allowed within a transaction() block. "
                "Use 'with compressed_dict.transaction() as d:' to modify the dictionary."
            )

        # If no default is provided, use the standard dict.pop() behavior
        if default is None:
            return self._working_dict.pop(key)

        return self._working_dict.pop(key, default)

    def to_plain_dict(self) -> Dict[K, V]:
        """
        Get the plain dictionary representation

        Returns:
            Plain dictionary
        """
        return cast(
            Dict[K, V], json.loads(json.dumps(self.to_dict(), cls=FhirJSONEncoder))
        )
