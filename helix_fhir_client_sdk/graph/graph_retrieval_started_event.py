from dataclasses import dataclass


@dataclass(slots=True)
class GraphRetrievalStartedEvent:
    """
    Emitted exactly once by simulate_graph_by_resource_type_async(), before
    the start resource is fetched — the first thing the method does. Useful
    for "connecting..." progress UI.
    """

    start_resource_type: str
    """The graph definition's start resource type (e.g. "Patient")."""

    url: str
    """The connection's base FHIR server URL. Not the full query URL with
    params — see ResourceTypeStartedEvent.url's docstring for why."""
