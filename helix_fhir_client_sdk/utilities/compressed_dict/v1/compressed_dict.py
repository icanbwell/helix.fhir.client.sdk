from typing import Dict, Optional, Literal, Iterator, Tuple, cast

import msgpack
import zlib

CompressedDictStorageMode = Literal["raw", "msgpack", "compressed_msgpack"]


class CompressedDict[K, V]:
    def __init__(
        self,
        initial_dict: Optional[Dict[K, V]] = None,
        storage_mode: CompressedDictStorageMode = "raw",
    ):
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

        # Private storage options
        self._raw_dict: Dict[K, V] = {}
        self._serialized_dict: Dict[K, bytes] = {}

        # Populate initial dictionary if provided
        if initial_dict:
            for key, value in initial_dict.items():
                self[key] = value

    @staticmethod
    def _serialize_value(value: V, compressed: bool = False) -> bytes:
        """
        Serialize a value using MessagePack

        Args:
            value: Value to serialize
            compressed: Whether to apply compression

        Returns:
            Serialized bytes
        """
        # Serialize using MessagePack
        packed = msgpack.packb(
            value,
            use_bin_type=True,  # Preserve string/bytes distinction
            use_single_float=True,  # More compact float representation
        )

        # Optional compression
        if compressed:
            packed = zlib.compress(packed, level=zlib.Z_BEST_COMPRESSION)

        return packed

    @staticmethod
    def _deserialize_value(serialized_value: bytes, compressed: bool = False) -> V:
        """
        Deserialize a value from MessagePack

        Args:
            serialized_value: Serialized value bytes
            compressed: Whether the value was compressed

        Returns:
            Deserialized value
        """
        # Decompress if needed
        to_unpack = (
            zlib.decompress(serialized_value) if compressed else serialized_value
        )

        # Deserialize
        return cast(
            V,
            msgpack.unpackb(
                to_unpack,
                raw=False,  # Convert to strings
                strict_map_key=False,  # Handle potential key type variations
            ),
        )

    def __getitem__(self, key: K) -> V:
        """
        Retrieve a value based on storage mode

        Args:
            key: Dictionary key

        Returns:
            Value associated with the key
        """
        # Raw storage mode
        if self._storage_mode == "raw":
            return self._raw_dict[key]

        # Serialized storage modes
        if key not in self._serialized_dict:
            raise KeyError(key)

        # Deserialize based on storage mode
        if self._storage_mode == "msgpack":
            return self._deserialize_value(self._serialized_dict[key], compressed=False)
        elif self._storage_mode == "compressed_msgpack":
            return self._deserialize_value(self._serialized_dict[key], compressed=True)

        raise ValueError(f"Invalid storage mode: {self._storage_mode}")

    def __setitem__(self, key: K, value: V) -> None:
        """
        Set a value based on storage mode

        Args:
            key: Dictionary key
            value: Value to store
        """
        # Reset previous storage
        if self._storage_mode == "raw":
            self._raw_dict[key] = value
            # Ensure serialized dict is cleared for this key
            self._serialized_dict.pop(key, None)
        elif self._storage_mode == "msgpack":
            self._serialized_dict[key] = self._serialize_value(value, compressed=False)
            # Ensure raw dict is cleared for this key
            self._raw_dict.pop(key, None)
        elif self._storage_mode == "compressed_msgpack":
            self._serialized_dict[key] = self._serialize_value(value, compressed=True)
            # Ensure raw dict is cleared for this key
            self._raw_dict.pop(key, None)

    def __delitem__(self, key: K) -> None:
        """
        Delete an item based on storage mode

        Args:
            key: Key to delete
        """
        if self._storage_mode == "raw":
            del self._raw_dict[key]
        else:
            del self._serialized_dict[key]

    def __contains__(self, key: object) -> bool:
        """
        Check if a key exists based on storage mode

        Args:
            key: Key to check

        Returns:
            Whether the key exists
        """
        if self._storage_mode == "raw":
            return key in self._raw_dict
        return key in self._serialized_dict

    def __len__(self) -> int:
        """
        Get the number of items

        Returns:
            Number of items in the dictionary
        """
        if self._storage_mode == "raw":
            return len(self._raw_dict)
        return len(self._serialized_dict)

    def __iter__(self) -> Iterator[K]:
        """
        Iterate over keys

        Returns:
            Iterator of keys
        """
        if self._storage_mode == "raw":
            return iter(self._raw_dict)
        return iter(self._serialized_dict)

    def keys(self) -> Iterator[K]:
        """
        Get an iterator of keys

        Returns:
            Iterator of keys
        """
        return self.__iter__()

    def values(self) -> Iterator[V]:
        """
        Get an iterator of values

        Returns:
            Iterator of values
        """
        if self._storage_mode == "raw":
            for key, value in self._raw_dict.items():
                yield value

        # Deserialize values based on storage mode
        for serialized_value in self._serialized_dict.values():
            if self._storage_mode == "msgpack":
                yield self._deserialize_value(serialized_value, compressed=False)
            elif self._storage_mode == "compressed_msgpack":
                yield self._deserialize_value(serialized_value, compressed=True)

    def items(self) -> Iterator[Tuple[K, V]]:
        """
        Get an iterator of key-value pairs

        Returns:
            Iterator of key-value pairs
        """
        if self._storage_mode == "raw":
            for key, value in self._raw_dict.items():
                yield key, value

        # Deserialize values based on storage mode
        for key, serialized_value in self._serialized_dict.items():
            if self._storage_mode == "msgpack":
                yield key, self._deserialize_value(serialized_value, compressed=False)
            elif self._storage_mode == "compressed_msgpack":
                yield key, self._deserialize_value(serialized_value, compressed=True)

    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        """
        Get a value with a default

        Args:
            key: Key to retrieve
            default: Default value if key not found

        Returns:
            Value or default
        """
        try:
            return self[key]
        except KeyError:
            return default

    def to_dict(self) -> Dict[K, V]:
        """
        Convert to a standard dictionary

        Returns:
            Standard dictionary with all values
        """
        return dict(self.items())

    @classmethod
    def from_dict(
        cls, input_dict: Dict[K, V], storage_mode: CompressedDictStorageMode = "raw"
    ) -> "CompressedDict[K, V]":
        """
        Create a MsgPackDict from a standard dictionary

        Args:
            input_dict: Input dictionary
            storage_mode: Storage mode to use

        Returns:
            MsgPackDict instance
        """
        return cls(input_dict, storage_mode=storage_mode)

    def __repr__(self) -> str:
        """
        String representation of the dictionary

        Returns:
            String representation
        """
        return (
            f"MsgPackDict(storage_mode='{self._storage_mode}', "
            f"items={dict(self.items())})"
        )
