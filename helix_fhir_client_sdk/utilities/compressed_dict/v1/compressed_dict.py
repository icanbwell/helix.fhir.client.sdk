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
        self._serialized_dict: Optional[bytes] = None

        # Populate initial dictionary if provided
        if initial_dict:
            for key, value in initial_dict.items():
                self[key] = value

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
        return self._get_dict()[key]

    def __setitem__(self, key: K, value: V) -> None:
        """
        Set a value

        Args:
            key: Dictionary key
            value: Value to store
        """
        if self._storage_mode == "raw":
            # Direct storage for raw mode
            self._raw_dict[key] = value
        else:
            # For serialized modes, create a new dict
            current_dict = self._get_dict()
            current_dict[key] = value

            # Reserialize
            if self._storage_mode == "msgpack":
                self._serialized_dict = self._serialize_dict(
                    current_dict, compressed=False
                )
            elif self._storage_mode == "compressed_msgpack":
                self._serialized_dict = self._serialize_dict(
                    current_dict, compressed=True
                )

    def __delitem__(self, key: K) -> None:
        """
        Delete an item

        Args:
            key: Key to delete
        """
        if self._storage_mode == "raw":
            del self._raw_dict[key]
        else:
            # For serialized modes, create a new dict
            current_dict = self._get_dict()
            del current_dict[key]

            # Reserialize
            if self._storage_mode == "msgpack":
                self._serialized_dict = self._serialize_dict(
                    current_dict, compressed=False
                )
            elif self._storage_mode == "compressed_msgpack":
                self._serialized_dict = self._serialize_dict(
                    current_dict, compressed=True
                )

    def __contains__(self, key: object) -> bool:
        """
        Check if a key exists

        Args:
            key: Key to check

        Returns:
            Whether the key exists
        """
        return key in self._get_dict()

    def __len__(self) -> int:
        """
        Get the number of items

        Returns:
            Number of items in the dictionary
        """
        return len(self._get_dict())

    def __iter__(self) -> Iterator[K]:
        """
        Iterate over keys

        Returns:
            Iterator of keys
        """
        return iter(self._get_dict())

    def keys(self) -> Iterator[K]:
        """
        Get an iterator of keys

        Returns:
            Iterator of keys
        """
        for k in self._get_dict().keys():
            yield k

    def values(self) -> Iterator[V]:
        """
        Get an iterator of values

        Returns:
            Iterator of values
        """
        for v in self._get_dict().values():
            yield v

    def items(self) -> Iterator[Tuple[K, V]]:
        """
        Get an iterator of key-value pairs

        Returns:
            Iterator of key-value pairs
        """
        for c in self._get_dict().items():
            yield c

    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        """
        Get a value with a default

        Args:
            key: Key to retrieve
            default: Default value if key not found

        Returns:
            Value or default
        """
        return self._get_dict().get(key, default)

    def to_dict(self) -> Dict[K, V]:
        """
        Convert to a standard dictionary

        Returns:
            Standard dictionary with all values
        """
        return dict(self._get_dict())

    @classmethod
    def from_dict(
        cls, input_dict: Dict[K, V], storage_mode: CompressedDictStorageMode = "raw"
    ) -> "CompressedDict[K, V]":
        """
        Create a CompressedDict from a standard dictionary

        Args:
            input_dict: Input dictionary
            storage_mode: Storage mode to use

        Returns:
            CompressedDict instance
        """
        return cls(input_dict, storage_mode=storage_mode)

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
