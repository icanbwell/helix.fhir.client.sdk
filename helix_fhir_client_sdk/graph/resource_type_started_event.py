from dataclasses import dataclass


@dataclass(slots=True)
class ResourceTypeStartedEvent:
    """
    Emitted by simulate_graph_by_resource_type_async() right before it begins
    retrieving one GraphDefinition link's resource type(s), or the start
    resource itself. Fires once per link (mirroring
    ResourceTypeCompletionEvent), before any HTTP request for that link has
    completed.
    """

    resource_types: list[str]
    """Resource type(s) about to be retrieved, taken from the graph
    definition's declared target types for this link (or [start] for the
    start resource) — not yet known-actual, since nothing has been fetched
    yet. Contrast with ResourceTypeCompletionEvent.resource_types, which
    reflects what was actually returned."""

    graph_depth: int
    """Same semantics as ResourceTypeCompletionEvent.graph_depth: 0 for links
    directly off the start resource, incremented once per level of
    target.link nesting."""

    url: str
    """The connection's base FHIR server URL (e.g. "https://example.com/fhir").
    Unlike ResourceTypeCompletionEvent.urls, this is NOT the full query URL
    with params — the specific request for this resource type hasn't been
    constructed yet when this event fires, since its query parameters come
    from substituting the parent bundle's actual resource references into
    the link's target.params template, which happens deeper in the request
    pipeline than this event's firing point."""

    link_index: int
    """-1 for the start resource (not processed via AsyncParallelProcessor, so
    it has no row index). For links, the 0-based index of this link within
    the current graph_depth pass's row list — combined with graph_depth,
    forms a stable key for pairing this event with its corresponding
    ResourceTypeCompletionEvent, since resource_types alone is not always
    unique (a link can declare multiple types, two links at the same depth
    can declare the same type, and a type can recur at a later depth)."""
