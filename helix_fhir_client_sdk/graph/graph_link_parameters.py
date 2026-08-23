from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from logging import Logger

from compressedfhir.fhir.fhir_bundle_entry_list import FhirBundleEntryList

from helix_fhir_client_sdk.graph.resource_type_completion_event import (
    ResourceTypeCompletionEvent,
)
from helix_fhir_client_sdk.graph.resource_type_started_event import (
    ResourceTypeStartedEvent,
)
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

    on_resource_type_started: Callable[[ResourceTypeStartedEvent], Awaitable[None]] | None = None
    """Optional callback fired once per row (GraphDefinitionLink) right
    before that link's resources begin retrieving. None for callers that
    don't use simulate_graph_by_resource_type_async's per-resource-type
    hooks (e.g. simulate_graph_async)."""

    graph_depth: int = 0
    """The graph_depth of the current outer-loop pass this row belongs to.
    Only meaningful together with on_resource_type_started; unused
    otherwise."""

    url: str = ""
    """The connection's base FHIR server URL for this call, passed straight
    through to ResourceTypeStartedEvent.url (see that dataclass's docstring
    for why it's the base URL and not the full query URL). Only meaningful
    together with on_resource_type_started; unused otherwise."""

    on_resource_type_completed: Callable[[ResourceTypeCompletionEvent], Awaitable[None]] | None = None
    """Optional callback fired if this row (GraphDefinitionLink) raises while
    being processed, so a matching completion event still reaches callers
    that already got on_resource_type_started for this row. None for callers
    that don't use simulate_graph_by_resource_type_async's per-resource-type
    hooks (e.g. simulate_graph_async)."""
