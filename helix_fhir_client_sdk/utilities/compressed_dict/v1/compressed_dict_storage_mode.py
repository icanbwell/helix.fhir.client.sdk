import dataclasses
from typing import Literal, TypeAlias

CompressedDictStorageType: TypeAlias = Literal["raw", "msgpack", "compressed_msgpack"]


@dataclasses.dataclass(slots=True)
class CompressedDictStorageMode:
    storage_type: CompressedDictStorageType = "compressed_msgpack"
