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

    client_person_id: str
    """Caller-supplied, opaque identifier for the person this call belongs
    to. Not interpreted by this SDK in any way — echoed back exactly as
    provided, purely so a callback shared across multiple concurrent
    simulate_graph_by_resource_type_async() calls can tell them apart."""

    connection_name: str
    """Caller-supplied, opaque display name for the connection this call
    belongs to. Not interpreted by this SDK in any way — echoed back
    exactly as provided, for the same reason as client_person_id."""
