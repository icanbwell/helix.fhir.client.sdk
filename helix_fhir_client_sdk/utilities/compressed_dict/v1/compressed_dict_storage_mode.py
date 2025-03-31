import dataclasses
from typing import Literal


CompressedDictDictStorageType = Literal["raw", "msgpack", "compressed_msgpack"]


@dataclasses.dataclass
class CompressedDictStorageMode:
    storage_type: CompressedDictDictStorageType = "compressed_msgpack"
