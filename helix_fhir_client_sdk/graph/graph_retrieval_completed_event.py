from dataclasses import dataclass


@dataclass(slots=True)
class GraphRetrievalCompletedEvent:
    """
    Emitted exactly once by simulate_graph_by_resource_type_async(), after
    every resource in the graph has been yielded — the last thing the method
    does before returning (including the early-return path where the start
    resource itself returned zero results). Useful for "done" progress UI.
    """

    resource_types: list[str]
    """Distinct resource type(s) actually retrieved across the whole graph
    traversal (start resource + every link, every depth), sorted. Empty if
    the start resource itself returned zero results."""

    total_resource_count: int
    """Sum of get_resource_count() across every FhirGetResponse yielded
    during this call, including the start resource. 0 if the start resource
    returned zero results."""

    max_graph_depth: int
    """The deepest graph_depth value at which any link actually had
    resources to process (0 if only the start resource was retrieved, or if
    the start resource returned zero results)."""

    urls: list[str]
    """Union of every actual URL queried across the whole graph traversal
    (start resource + every link, every depth), params included. Contains
    at least the start resource's URL even if it returned zero results — a
    request was still made, it just came back empty — whereas
    resource_types is empty in that case, since nothing was actually
    retrieved. This event always fires exactly once, empty-result case
    included, since callers need a definitive "done" signal either way."""
