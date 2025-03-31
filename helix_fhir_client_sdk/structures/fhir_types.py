from typing import Any, Optional, Dict

from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict import (
    CompressedDict,
)
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)


class FhirResource(CompressedDict[str, Any]):
    def __init__(
        self,
        *,
        initial_dict: Optional[Dict[str, Any]] = None,
        storage_mode: CompressedDictStorageMode,
    ) -> None:
        super().__init__(
            initial_dict=initial_dict,
            storage_mode=storage_mode,
            properties_to_cache=["resourceType", "id"],
        )
