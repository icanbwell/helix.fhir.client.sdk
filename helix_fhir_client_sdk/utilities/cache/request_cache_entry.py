import dataclasses
from datetime import datetime
from typing import Optional

from compressedfhir.fhir.fhir_bundle_entry import FhirBundleEntry


@dataclasses.dataclass(slots=True, weakref_slot=True)
class RequestCacheEntry:
    """
    Represents a cache entry for FHIR requests.
    """

    id_: str
    resource_type: str
    status: int | None
    bundle_entry: FhirBundleEntry | None
    last_modified: Optional[datetime]
    etag: Optional[str]
