from dataclasses import dataclass
from typing import Literal


@dataclass(slots=True)
class ResourceTypeCompletionEvent:
    """
    Emitted by simulate_graph_by_resource_type_async() after every resource that
    belongs to one GraphDefinition link (usually one resource type, occasionally
    more than one if the link's `target` array names several types) has been
    yielded to the caller. There is nothing left to wait for regarding these
    resource type(s) at this graph depth once this event fires.
    """

    resource_types: list[str]
    """Distinct resource type(s) actually returned for the completed link, taken
    from each yielded FhirGetResponse.resource_type — not from the graph
    definition's declared target types, so this reflects what was actually
    fetched. When a link returns zero resources, this falls back to the
    link's declared target type(s) instead of an empty list, so a caller that
    received ResourceTypeStartedEvent for this link always receives a
    matching completion event — use resource_count == 0 to distinguish this
    fallback case from a real non-empty result."""

    resource_count: int
    """Total resource count across every FhirGetResponse chunk yielded for this
    link (sum of each chunk's get_resource_count())."""

    graph_depth: int
    """0 for links directly off the start resource; incremented once per pass
    through simulate_graph_by_resource_type_async's outer while loop, i.e. once
    per level of target.link nesting. A resource type can recur at a later
    depth (e.g. Practitioner reached both via Patient.generalPractitioner and,
    later, Encounter.participant) — callers should treat this as "retrieving
    again", not a bug."""

    urls: list[str]
    """The actual URL(s) that were queried to produce this event's
    resources — one per FhirGetResponse chunk that contributed to it
    (usually one, occasionally more if the link had multiple targets or the
    response was paginated), params included (e.g.
    "https://example.com/fhir/AllergyIntolerance?patient=123"). Lets a
    callback shared across multiple concurrent
    simulate_graph_by_resource_type_async() calls tell which
    server/patient/call this event belongs to, since the patient/resource id
    is already embedded in the URL as a path or query parameter."""

    link_index: int
    """Same semantics as ResourceTypeStartedEvent.link_index — pairs this
    event with the ResourceTypeStartedEvent that preceded it. See that
    field's docstring for the important caveat that (graph_depth,
    link_index) is only globally unique at graph_depth == 0; at
    graph_depth >= 1 it is unique only within the single parallel-
    processing batch this link belongs to, and a depth can contain more
    than one such batch."""

    client_person_id: str
    """Caller-supplied, opaque identifier for the person this call belongs
    to. Not interpreted by this SDK in any way — echoed back exactly as
    provided, purely so a callback shared across multiple concurrent
    simulate_graph_by_resource_type_async() calls can tell them apart."""

    connection_name: str
    """Caller-supplied, opaque display name for the connection this call
    belongs to. Not interpreted by this SDK in any way — echoed back
    exactly as provided, for the same reason as client_person_id."""

    outcome: Literal["success", "empty", "not_found", "scope_denied", "error"]
    """Precise classification of why resource_count is what it is:
    "success" (resource_count > 0); "empty" (zero resources, no specific
    reason — e.g. a reverse-link had no matching references, or this event
    was fired for a cancelled fetch, which is never classified as "error" —
    see error_type/error_message below); "not_found" (the source explicitly
    returned 404 for the requested resource(s)); "scope_denied" (the fetch
    never happened because the auth scope disallowed every one of the
    link's declared target types); "error" (the fetch raised — only
    possible when the caller opted into continue_on_resource_type_error;
    otherwise a raised fetch fires this event with outcome="error" and then
    the exception propagates, aborting the traversal — or the fetch came
    back with a non-404 unsuccessful HTTP status, which this SDK's retry
    client returns rather than raises for, e.g. 400/403). One link can declare
    more than one target type and so span responses with mixed outcomes —
    this field reports one outcome for the whole link event using the
    precedence above (success beats everything; a single successful target
    makes the whole link "success" even if a sibling target within the same
    link was denied or not found)."""

    error_type: str | None
    """The failed fetch's exception class name (e.g. "RuntimeError"), set
    only when outcome == "error". When the failure was a non-404
    unsuccessful HTTP status that this SDK's retry client returned rather
    than raised for, there is no exception to name, so this is synthesized
    as "HttpStatus<code>" (e.g. "HttpStatus403") — that prefix is how a
    caller tells the two error sources apart. None for every other
    outcome."""

    error_message: str | None
    """str(exception) for the failed fetch, or "Fetch failed with HTTP
    status <code>" for a returned-not-raised HTTP error status. Set only
    when outcome == "error"; None for every other outcome."""
