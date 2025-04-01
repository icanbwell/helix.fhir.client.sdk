import dataclasses
from typing import Literal, TypeAlias

CompressedDictStorageType: TypeAlias = Literal[
    "raw", "compressed", "msgpack", "compressed_msgpack"
]


@dataclasses.dataclass(slots=True)
class CompressedDictStorageMode:
    storage_type: CompressedDictStorageType = "compressed_msgpack"

    @classmethod
    def default(cls) -> "CompressedDictStorageMode":
        return cls(storage_type="compressed_msgpack")
