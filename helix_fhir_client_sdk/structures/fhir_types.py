from typing import TypeAlias, Any

from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict import (
    CompressedDict,
)

FhirResource: TypeAlias = CompressedDict[str, Any]
