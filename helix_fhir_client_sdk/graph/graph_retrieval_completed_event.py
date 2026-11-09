from dataclasses import dataclass


@dataclass(slots=True)
class GraphRetrievalCompletedEvent:
    """
    Emitted exactly once by simulate_graph_by_resource_type_async(),
    simulate_graph_async(), and simulate_graph_streaming_async(), after the
    traversal finishes retrieving every resource in the graph — the last
    thing each of those methods does before returning (including the
    early-return path where the start resource itself returned zero
    results). Useful for "done" progress UI.
    """

    resource_types: list[str]
    """Distinct resource type(s) actually retrieved across the whole graph
    traversal (start resource + every link, every depth), sorted. Empty if
    the start resource itself returned zero results."""

    total_resource_count: int
    """Sum of get_resource_count() across every FhirGetResponse retrieved
    during this call, including the start resource — yielded individually
    by simulate_graph_by_resource_type_async(), or accumulated into one
    combined response by simulate_graph_async()/simulate_graph_streaming_async().
    0 if the start resource returned zero results."""

    max_graph_depth: int
    """The deepest graph_depth value at which any link actually had
    resources to process (0 if only the start resource was retrieved, or if
    the start resource returned zero results)."""

    urls: list[str]
    """Union of every actual URL queried across the whole graph traversal
    (start resource + every link, every depth), params included. May be
    empty if every queried resource was served from cache or was
    scope-denied (no real HTTP request made), not just on the start
    resource's zero-result path. This event fires exactly once per call —
    including when the traversal raises or the caller closes/abandons the
    generator early — except in the unavoidable Python limitation where a
    caller lets the generator become unreachable without an explicit
    break/aclose()."""

    client_person_id: str
    """Caller-supplied, opaque identifier for the person this call belongs
    to. Not interpreted by this SDK in any way — echoed back exactly as
    provided, purely so a callback shared across multiple concurrent calls
    (to any of the three emitting methods above) can tell them apart."""

    connection_name: str
    """Caller-supplied, opaque display name for the connection this call
    belongs to. Not interpreted by this SDK in any way — echoed back
    exactly as provided, for the same reason as client_person_id."""

    total_error_count: int
    """Count of resource types (including the start resource, if its own
    fetch failed) whose ResourceTypeCompletionEvent fired with
    outcome == "error" during this call. A real fetch failure — the number
    a caller would alert or retry on. Does not include scope-denials (see
    total_rejected_count) or not-found/empty results, since those are
    normal, non-failure outcomes."""

    total_rejected_count: int
    """Count of resource types whose ResourceTypeCompletionEvent fired with
    outcome == "scope_denied" during this call. Kept separate from
    total_error_count because scope-denial is an expected authorization
    outcome, not a failure — folding it into the error count would make
    error-rate alerting fire on routine, by-design scope restrictions."""
