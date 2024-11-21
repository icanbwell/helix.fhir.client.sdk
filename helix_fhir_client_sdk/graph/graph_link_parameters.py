from dataclasses import dataclass
from typing import Optional, List

from helix_fhir_client_sdk.fhir_bundle import BundleEntry
from helix_fhir_client_sdk.loggers.fhir_logger import FhirLogger
from helix_fhir_client_sdk.utilities.fhir_scope_parser import FhirScopeParser
from helix_fhir_client_sdk.utilities.request_cache import RequestCache


@dataclass
class GraphLinkParameters:
    """
    This class contains the parameters for a graph target
    """

    parent_bundle_entries: List[BundleEntry] | None

    logger: Optional[FhirLogger]

    cache: RequestCache

    scope_parser: FhirScopeParser

    max_concurrent_tasks: Optional[int]
