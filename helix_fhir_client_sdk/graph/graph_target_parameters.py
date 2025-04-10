from dataclasses import dataclass
from typing import Optional

from compressedfhir.fhir.fhir_bundle_entry_list import FhirBundleEntryList
from logging import Logger
from helix_fhir_client_sdk.utilities.fhir_scope_parser import FhirScopeParser
from helix_fhir_client_sdk.utilities.cache.request_cache import RequestCache


@dataclass(slots=True)
class GraphTargetParameters:
    """
    This class contains the parameters for a graph target
    """

    path: Optional[str]
    """ path to the target """

    parent_bundle_entries: FhirBundleEntryList | None
    """ parent bundle entry """

    logger: Optional[Logger]
    """ logger """

    cache: RequestCache

    scope_parser: FhirScopeParser

    max_concurrent_tasks: Optional[int]
