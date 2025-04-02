import dataclasses
from typing import Literal, TypeAlias

CompressedDictStorageType: TypeAlias = Literal[
    "raw", "compressed", "msgpack", "compressed_msgpack"
]
"""
CompressedDictStorageType is a type alias for the different storage types
raw: No compression
compressed: Compressed using zlib
msgpack: Compressed using msgpack
compressed_msgpack: Compressed using msgpack with zlib
"""


@dataclasses.dataclass(slots=True)
class CompressedDictStorageMode:
    """
    CompressedDictStorageMode is a dataclass that defines the storage mode
    """

    storage_type: CompressedDictStorageType = "compressed"
    """
    CompressedDictStorageType is a type alias for the different storage types
    raw: No compression
    compressed: Compressed using zlib
    msgpack: Compressed using msgpack
    compressed_msgpack: Compressed using msgpack with zlib
    """

    @classmethod
    def default(cls) -> "CompressedDictStorageMode":
        """
        Returns the default storage mode
        """
        return cls(storage_type="compressed")

    @classmethod
    def raw(cls) -> "CompressedDictStorageMode":
        """
        Returns the default storage mode
        """
        return cls(storage_type="raw")

    @classmethod
    def compressed(cls) -> "CompressedDictStorageMode":
        """
        Returns the default storage mode
        """
        return cls(storage_type="compressed")
