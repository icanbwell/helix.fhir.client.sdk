from dataclasses import dataclass
from logging import Logger

from compressedfhir.fhir.fhir_bundle_entry_list import FhirBundleEntryList

from helix_fhir_client_sdk.utilities.cache.request_cache import RequestCache
from helix_fhir_client_sdk.utilities.fhir_scope_parser import FhirScopeParser


@dataclass(slots=True)
class GraphLinkParameters:
    """
    This class contains the parameters for a graph target
    """

    parent_bundle_entries: FhirBundleEntryList | None

    logger: Logger | None

    cache: RequestCache

    scope_parser: FhirScopeParser

    max_concurrent_tasks: int | None
