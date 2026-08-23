# Error & Rejection Visibility for `simulate_graph_by_resource_type_async()` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every `ResourceTypeCompletionEvent` a precise `outcome` (success/empty/not_found/scope_denied/error) instead of an undifferentiated zero-count, add error/rejection rollups to `GraphRetrievalCompletedEvent`, and add an opt-in `continue_on_resource_type_error` flag so one resource type's fetch failure no longer has to abort the whole `$graph` traversal.

**Architecture:** All changes live in the existing per-resource-type completion-hook machinery in `helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py` plus the four event dataclasses under `helix_fhir_client_sdk/graph/`. No new files except one private, module-local result-carrier dataclass (`_LinkFetchResult`) needed to let a link's fetch failure travel back to the consumer loop as data instead of as a raised exception when the caller opts into `continue_on_resource_type_error`.

**Tech Stack:** Python 3.13, dataclasses (`slots=True`), `asyncio`, `aioresponses` for HTTP-level test mocking, `pytest` + `pytest-asyncio`, `uv`, `mypy`, `ruff`.

**Spec:** `docs/superpowers/specs/2026-08-23-resource-type-error-visibility-design.md`

## Global Constraints

- Ticket: every commit message starts with `DCON-5229` (not `DCON-4509` — that ticket has been reassigned to unrelated work; see the design spec's header).
- `continue_on_resource_type_error` defaults to `False` — every existing caller that passes none of the four callbacks or this new flag must see **zero behavior change**. This is a hard requirement carried over from the original completion-hook feature's own design.
- `asyncio.CancelledError` is never treated as a resource-type error, in either mode — it always propagates immediately after firing its completion event (this was already fixed for the existing except-clauses in commit `4d4f8ec` on this branch; do not regress it).
- The start resource's own fetch failure is always fatal, in every mode.
- A failed link's nested `target.link` children are skipped entirely (no parent bundle to traverse from) — this already happens naturally today (a link that raises never reaches the `if target.link: parent_link_map.append(...)` line), so no code change is required for this constraint — it is verified by a test in Task 4, not implemented by new code.
- Tests live in `helix_fhir_client_sdk/graph/test/` — no pytest fixtures, just the existing `TestGraphProcessor(FhirClient)` / `get_graph_processor()` pattern and `aioresponses()` HTTP-level mocking (see `helix_fhir_client_sdk/graph/test/test_simulate_graph_processor_mixin.py` and `test_simulate_graph_by_resource_type_async_completion_hook.py`).
- Run `uv run pytest helix_fhir_client_sdk/graph/test/ -v` and `uv run mypy helix_fhir_client_sdk/` after every task; run the full `uv run pytest helix_fhir_client_sdk/ -v` regression suite before the final commit.

---

## Task 1: Add `outcome`/`error_type`/`error_message` to `ResourceTypeCompletionEvent`

**Files:**
- Modify: `helix_fhir_client_sdk/graph/resource_type_completion_event.py`
- Modify: `helix_fhir_client_sdk/graph/test/test_resource_type_completion_event.py`

**Interfaces:**
- Produces: `ResourceTypeCompletionEvent.outcome: Literal["success", "empty", "not_found", "scope_denied", "error"]`, `ResourceTypeCompletionEvent.error_type: str | None`, `ResourceTypeCompletionEvent.error_message: str | None` — required (no default), consumed by every construction site in Task 3 and by any test/caller that builds this event directly.

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `helix_fhir_client_sdk/graph/test/test_resource_type_completion_event.py` with:

```python
from helix_fhir_client_sdk.graph.resource_type_completion_event import (
    ResourceTypeCompletionEvent,
)


def test_resource_type_completion_event_construction() -> None:
    event = ResourceTypeCompletionEvent(
        resource_types=["Condition"],
        resource_count=12,
        graph_depth=1,
        urls=["https://example.com/fhir/Condition?patient=123"],
        link_index=0,
        client_person_id="client-1",
        connection_name="Aetna Sandbox",
        outcome="success",
        error_type=None,
        error_message=None,
    )
    assert event.resource_types == ["Condition"]
    assert event.resource_count == 12
    assert event.graph_depth == 1
    assert event.urls == ["https://example.com/fhir/Condition?patient=123"]
    assert event.link_index == 0
    assert event.client_person_id == "client-1"
    assert event.connection_name == "Aetna Sandbox"
    assert event.outcome == "success"
    assert event.error_type is None
    assert event.error_message is None


def test_resource_type_completion_event_multiple_types() -> None:
    # A single GraphDefinition link's `target` array can name more than one type
    # (e.g. a link with both AllergyIntolerance and CarePlan targets), so this
    # must accept more than one resource type — and more than one queried URL —
    # per event.
    event = ResourceTypeCompletionEvent(
        resource_types=["AllergyIntolerance", "CarePlan"],
        resource_count=5,
        graph_depth=0,
        urls=[
            "https://example.com/fhir/AllergyIntolerance?patient=123",
            "https://example.com/fhir/CarePlan?patient=123",
        ],
        link_index=0,
        client_person_id="client-1",
        connection_name="Aetna Sandbox",
        outcome="success",
        error_type=None,
        error_message=None,
    )
    assert len(event.resource_types) == 2
    assert len(event.urls) == 2
    assert event.client_person_id == "client-1"
    assert event.connection_name == "Aetna Sandbox"


def test_resource_type_completion_event_error_outcome() -> None:
    event = ResourceTypeCompletionEvent(
        resource_types=["AllergyIntolerance"],
        resource_count=0,
        graph_depth=0,
        urls=[],
        link_index=0,
        client_person_id="client-1",
        connection_name="Aetna Sandbox",
        outcome="error",
        error_type="RuntimeError",
        error_message="simulated network failure",
    )
    assert event.outcome == "error"
    assert event.error_type == "RuntimeError"
    assert event.error_message == "simulated network failure"


def test_resource_type_completion_event_not_found_outcome() -> None:
    event = ResourceTypeCompletionEvent(
        resource_types=["Condition"],
        resource_count=0,
        graph_depth=0,
        urls=["https://example.com/fhir/Condition?patient=123"],
        link_index=0,
        client_person_id="",
        connection_name="",
        outcome="not_found",
        error_type=None,
        error_message=None,
    )
    assert event.outcome == "not_found"


def test_resource_type_completion_event_scope_denied_outcome() -> None:
    event = ResourceTypeCompletionEvent(
        resource_types=["Condition"],
        resource_count=0,
        graph_depth=0,
        urls=[],
        link_index=0,
        client_person_id="",
        connection_name="",
        outcome="scope_denied",
        error_type=None,
        error_message=None,
    )
    assert event.outcome == "scope_denied"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest helix_fhir_client_sdk/graph/test/test_resource_type_completion_event.py -v`
Expected: FAIL — `TypeError: ResourceTypeCompletionEvent.__init__() got an unexpected keyword argument 'outcome'`

- [ ] **Step 3: Add the new fields**

Replace the full contents of `helix_fhir_client_sdk/graph/resource_type_completion_event.py` with:

```python
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
    the exception propagates, aborting the traversal). One link can declare
    more than one target type and so span responses with mixed outcomes —
    this field reports one outcome for the whole link event using the
    precedence above (success beats everything; a single successful target
    makes the whole link "success" even if a sibling target within the same
    link was denied or not found)."""

    error_type: str | None
    """The failed fetch's exception class name (e.g. "RuntimeError"), set
    only when outcome == "error". None for every other outcome."""

    error_message: str | None
    """str(exception) for the failed fetch, set only when outcome ==
    "error". None for every other outcome."""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest helix_fhir_client_sdk/graph/test/test_resource_type_completion_event.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Type-check**

Run: `uv run mypy helix_fhir_client_sdk/graph/resource_type_completion_event.py helix_fhir_client_sdk/graph/test/test_resource_type_completion_event.py`
Expected: `Success: no issues found`

This will currently NOT fully pass repo-wide mypy/pytest, because `simulated_graph_processor_mixin.py` still constructs `ResourceTypeCompletionEvent` without the three new required keyword arguments — that is fixed in Task 3. Do not attempt to run the full suite yet.

- [ ] **Step 6: Commit**

```bash
git add helix_fhir_client_sdk/graph/resource_type_completion_event.py helix_fhir_client_sdk/graph/test/test_resource_type_completion_event.py
git commit -m "DCON-5229 add outcome/error_type/error_message fields to ResourceTypeCompletionEvent"
```

---

## Task 2: Add `total_error_count`/`total_rejected_count` to `GraphRetrievalCompletedEvent`

**Files:**
- Modify: `helix_fhir_client_sdk/graph/graph_retrieval_completed_event.py`
- Modify: `helix_fhir_client_sdk/graph/test/test_graph_retrieval_completed_event.py`

**Interfaces:**
- Produces: `GraphRetrievalCompletedEvent.total_error_count: int`, `GraphRetrievalCompletedEvent.total_rejected_count: int` — required (no default), consumed by the `finally` block in Task 3.

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `helix_fhir_client_sdk/graph/test/test_graph_retrieval_completed_event.py` with:

```python
from helix_fhir_client_sdk.graph.graph_retrieval_completed_event import (
    GraphRetrievalCompletedEvent,
)


def test_graph_retrieval_completed_event_construction() -> None:
    event = GraphRetrievalCompletedEvent(
        resource_types=["Patient", "AllergyIntolerance", "CarePlan"],
        total_resource_count=3,
        max_graph_depth=0,
        urls=[
            "https://example.com/fhir/Patient/123",
            "https://example.com/fhir/AllergyIntolerance?patient=123",
            "https://example.com/fhir/CarePlan?patient=123",
        ],
        client_person_id="client-1",
        connection_name="Aetna Sandbox",
        total_error_count=0,
        total_rejected_count=0,
    )
    assert event.resource_types == ["Patient", "AllergyIntolerance", "CarePlan"]
    assert event.total_resource_count == 3
    assert event.max_graph_depth == 0
    assert len(event.urls) == 3
    assert event.client_person_id == "client-1"
    assert event.connection_name == "Aetna Sandbox"
    assert event.total_error_count == 0
    assert event.total_rejected_count == 0


def test_graph_retrieval_completed_event_zero_results() -> None:
    # Fires even when the start resource itself returned zero results —
    # callers need a definitive "done" signal either way.
    event = GraphRetrievalCompletedEvent(
        resource_types=[],
        total_resource_count=0,
        max_graph_depth=0,
        urls=["https://example.com/fhir/Patient/123"],
        client_person_id="client-1",
        connection_name="Aetna Sandbox",
        total_error_count=0,
        total_rejected_count=0,
    )
    assert event.resource_types == []
    assert event.total_resource_count == 0
    assert event.client_person_id == "client-1"
    assert event.connection_name == "Aetna Sandbox"


def test_graph_retrieval_completed_event_error_and_rejection_rollups() -> None:
    event = GraphRetrievalCompletedEvent(
        resource_types=["Patient"],
        total_resource_count=1,
        max_graph_depth=0,
        urls=["https://example.com/fhir/Patient/123"],
        client_person_id="client-1",
        connection_name="Aetna Sandbox",
        total_error_count=2,
        total_rejected_count=1,
    )
    assert event.total_error_count == 2
    assert event.total_rejected_count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest helix_fhir_client_sdk/graph/test/test_graph_retrieval_completed_event.py -v`
Expected: FAIL — `TypeError: GraphRetrievalCompletedEvent.__init__() got an unexpected keyword argument 'total_error_count'`

- [ ] **Step 3: Add the new fields**

Replace the full contents of `helix_fhir_client_sdk/graph/graph_retrieval_completed_event.py` with:

```python
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
    provided, purely so a callback shared across multiple concurrent
    simulate_graph_by_resource_type_async() calls can tell them apart."""

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest helix_fhir_client_sdk/graph/test/test_graph_retrieval_completed_event.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Type-check**

Run: `uv run mypy helix_fhir_client_sdk/graph/graph_retrieval_completed_event.py helix_fhir_client_sdk/graph/test/test_graph_retrieval_completed_event.py`
Expected: `Success: no issues found`

Same caveat as Task 1: the repo-wide suite will not pass until Task 3 updates `simulated_graph_processor_mixin.py`'s single `GraphRetrievalCompletedEvent(...)` construction site.

- [ ] **Step 6: Commit**

```bash
git add helix_fhir_client_sdk/graph/graph_retrieval_completed_event.py helix_fhir_client_sdk/graph/test/test_graph_retrieval_completed_event.py
git commit -m "DCON-5229 add total_error_count/total_rejected_count rollups to GraphRetrievalCompletedEvent"
```

---

## Task 3: Classify `outcome` for every fired event, with zero control-flow change

**Files:**
- Modify: `helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py`
- Modify: `helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py`

**Interfaces:**
- Consumes: `ResourceTypeCompletionEvent` (Task 1), `GraphRetrievalCompletedEvent` (Task 2), `FhirScopeParser.scope_allows(resource_type: str, interaction: str = "read") -> bool` (existing), `FhirGetResponse.status: int` (existing).
- Produces: `SimulatedGraphProcessorMixin._fire_on_resource_type_completed_for_link(...) -> Literal["success", "empty", "not_found", "scope_denied", "error"]` — now returns the classified outcome instead of `None`; gains three new keyword-only parameters: `link_responses: list[FhirGetResponse]`, `scope_parser: FhirScopeParser`, `error: Exception | None = None`. Task 4 will pass a real `error` value; every call site in this task passes none (uses the default `None`).

At the end of this task, behavior is identical to before it (every failure still aborts the traversal exactly as today) — only the data carried on each fired event, and the two new graph-level rollup counts, become accurate.

- [ ] **Step 1: Write the failing tests**

Add these tests to the end of `helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py`:

```python
@pytest.mark.asyncio
async def test_resource_type_completed_outcome_success() -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    completed_events: list[ResourceTypeCompletionEvent] = []

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    with aioresponses() as m:
        mock_two_link_graph_responses(m)

        async for _ in graph_processor.simulate_graph_by_resource_type_async(
            id_="1",
            graph_json=TWO_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
            on_resource_type_completed=on_completed,
        ):
            pass

    assert all(e.outcome == "success" for e in completed_events)
    assert all(e.error_type is None and e.error_message is None for e in completed_events)


@pytest.mark.asyncio
async def test_resource_type_completed_outcome_empty_for_no_matching_references() -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    completed_events: list[ResourceTypeCompletionEvent] = []

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    with aioresponses() as m:
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Patient", "id": "1"},
        )

        async for _ in graph_processor.simulate_graph_by_resource_type_async(
            id_="1",
            graph_json=PATH_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
            on_resource_type_completed=on_completed,
        ):
            pass

    link_completed = [e for e in completed_events if e.link_index == 0]
    assert len(link_completed) == 1
    assert link_completed[0].outcome == "empty"


@pytest.mark.asyncio
async def test_resource_type_completed_outcome_not_found() -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    completed_events: list[ResourceTypeCompletionEvent] = []

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    with aioresponses() as m:
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Patient", "id": "1"},
        )
        m.get(
            "http://example.com/fhir/AllergyIntolerance?patient=1",
            status=404,
            payload={"resourceType": "OperationOutcome"},
        )
        m.get(
            "http://example.com/fhir/CarePlan?patient=1",
            payload={"resourceType": "CarePlan", "id": "1"},
        )

        async for _ in graph_processor.simulate_graph_by_resource_type_async(
            id_="1",
            graph_json=TWO_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
            on_resource_type_completed=on_completed,
        ):
            pass

    allergy_completed = [e for e in completed_events if e.resource_types == ["AllergyIntolerance"]]
    assert len(allergy_completed) == 1
    assert allergy_completed[0].outcome == "not_found"


@pytest.mark.asyncio
async def test_resource_type_completed_outcome_scope_denied() -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    completed_events: list[ResourceTypeCompletionEvent] = []
    graph_completed_events: list[GraphRetrievalCompletedEvent] = []

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    async def on_graph_completed(event: GraphRetrievalCompletedEvent) -> None:
        graph_completed_events.append(event)

    with aioresponses() as m:
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Patient", "id": "1"},
        )
        m.get(
            "http://example.com/fhir/CarePlan?patient=1",
            payload={"resourceType": "CarePlan", "id": "1"},
        )

        async for _ in graph_processor.simulate_graph_by_resource_type_async(
            id_="1",
            graph_json=TWO_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
            auth_scopes=["patient/CarePlan.read"],
            on_resource_type_completed=on_completed,
            on_graph_retrieval_completed=on_graph_completed,
        ):
            pass

    allergy_completed = [e for e in completed_events if e.resource_types == ["AllergyIntolerance"]]
    assert len(allergy_completed) == 1
    assert allergy_completed[0].outcome == "scope_denied"
    assert len(graph_completed_events) == 1
    assert graph_completed_events[0].total_rejected_count == 1
    assert graph_completed_events[0].total_error_count == 0


@pytest.mark.asyncio
async def test_resource_type_completed_outcome_error_and_graph_error_count() -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    completed_events: list[ResourceTypeCompletionEvent] = []
    graph_completed_events: list[GraphRetrievalCompletedEvent] = []

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    async def on_graph_completed(event: GraphRetrievalCompletedEvent) -> None:
        graph_completed_events.append(event)

    with aioresponses() as m:
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Patient", "id": "1"},
        )
        m.get(
            "http://example.com/fhir/AllergyIntolerance?patient=1",
            exception=RuntimeError("simulated network failure fetching link"),
        )
        m.get(
            "http://example.com/fhir/CarePlan?patient=1",
            payload={"resourceType": "CarePlan", "id": "1"},
        )

        with pytest.raises(FhirSenderException):
            async for _ in graph_processor.simulate_graph_by_resource_type_async(
                id_="1",
                graph_json=TWO_LINK_GRAPH,
                contained=False,
                max_concurrent_tasks=1,
                on_resource_type_completed=on_completed,
                on_graph_retrieval_completed=on_graph_completed,
            ):
                pass

    allergy_completed = [e for e in completed_events if e.resource_types == ["AllergyIntolerance"]]
    assert len(allergy_completed) == 1
    assert allergy_completed[0].outcome == "error"
    assert allergy_completed[0].error_type == "FhirSenderException"
    assert allergy_completed[0].error_message

    assert len(graph_completed_events) == 1
    assert graph_completed_events[0].total_error_count == 1
    assert graph_completed_events[0].total_rejected_count == 0


@pytest.mark.asyncio
async def test_resource_type_completed_outcome_error_for_start_resource() -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    completed_events: list[ResourceTypeCompletionEvent] = []
    graph_completed_events: list[GraphRetrievalCompletedEvent] = []

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    async def on_graph_completed(event: GraphRetrievalCompletedEvent) -> None:
        graph_completed_events.append(event)

    with aioresponses() as m:
        m.get(
            "http://example.com/fhir/Patient/1",
            exception=RuntimeError("simulated network failure fetching start resource"),
        )

        with pytest.raises(FhirSenderException):
            async for _ in graph_processor.simulate_graph_by_resource_type_async(
                id_="1",
                graph_json=TWO_LINK_GRAPH,
                contained=False,
                max_concurrent_tasks=1,
                on_resource_type_completed=on_completed,
                on_graph_retrieval_completed=on_graph_completed,
            ):
                pass

    assert len(completed_events) == 1
    assert completed_events[0].outcome == "error"
    assert completed_events[0].error_type == "FhirSenderException"
    assert len(graph_completed_events) == 1
    assert graph_completed_events[0].total_error_count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py -v -k "outcome"`
Expected: FAIL — `TypeError: ResourceTypeCompletionEvent.__init__() got an unexpected keyword argument 'outcome'` (raised from inside `simulated_graph_processor_mixin.py`, which does not pass it yet).

- [ ] **Step 3: Add `Literal` import**

In `helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py`, change:

```python
from typing import Any, cast
```

to:

```python
from typing import Any, Literal, cast
```

- [ ] **Step 4: Rewrite `_fire_on_resource_type_completed_for_link` to classify outcome**

In `helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py`, replace the entire `_fire_on_resource_type_completed_for_link` method with:

```python
    async def _fire_on_resource_type_completed_for_link(
        self,
        *,
        links: list[GraphDefinitionLink],
        context: ParallelFunctionContext,
        resource_types: list[str],
        resource_count_for_link: int,
        link_queried_urls: list[str],
        link_responses: list[FhirGetResponse],
        scope_parser: FhirScopeParser,
        graph_depth: int,
        on_resource_type_completed: Callable[[ResourceTypeCompletionEvent], Awaitable[None]] | None,
        client_person_id: str,
        connection_name: str,
        error: Exception | None = None,
    ) -> Literal["success", "empty", "not_found", "scope_denied", "error"]:
        """
        Classifies the outcome of one graph link's aggregated response batch
        and fires on_resource_type_completed (if a callback was supplied).
        Falls back to the link's declared target type(s) when the link
        returned zero resources (resource_types is empty), so a caller that
        received on_resource_type_started for this link always receives a
        matching completion event — see ResourceTypeCompletionEvent.outcome's
        docstring for the outcome precedence used when a link declares more
        than one target type.

        Always returns the classified outcome, even when
        on_resource_type_completed is None, so the caller can maintain the
        total_error_count/total_rejected_count rollups regardless of whether
        a per-link callback is registered.

        Extracted out of the traversal loop in
        _process_simulate_graph_by_resource_type_async to keep that loop's
        nesting shallow.
        """
        declared_types = sorted({target.type_ for target in links[context.task_index].target if target.type_})

        outcome: Literal["success", "empty", "not_found", "scope_denied", "error"]
        if error is not None:
            outcome = "error"
        elif resource_count_for_link > 0:
            outcome = "success"
        elif any(r.status == 404 for r in link_responses):
            outcome = "not_found"
        elif declared_types and not any(scope_parser.scope_allows(resource_type=t) for t in declared_types):
            outcome = "scope_denied"
        else:
            outcome = "empty"

        if on_resource_type_completed:
            reported_resource_types = resource_types or declared_types
            await on_resource_type_completed(
                ResourceTypeCompletionEvent(
                    resource_types=reported_resource_types,
                    resource_count=resource_count_for_link,
                    graph_depth=graph_depth,
                    urls=link_queried_urls,
                    link_index=context.task_index,
                    client_person_id=client_person_id,
                    connection_name=connection_name,
                    outcome=outcome,
                    error_type=type(error).__name__ if error is not None else None,
                    error_message=str(error) if error is not None else None,
                )
            )
        return outcome
```

- [ ] **Step 5: Update the per-link exception handler in `process_link_async_parallel_function`**

In the same file, replace:

```python
        except (Exception, asyncio.CancelledError):
            # Fire a matching completion event (if registered) before letting
            # the exception propagate, so a caller that already received
            # on_resource_type_started for this link doesn't get stuck
            # waiting forever for a completion event that will never come.
            # This is purely an additional signal — the exception is not
            # suppressed. asyncio.CancelledError is caught explicitly (it is
            # a BaseException, not an Exception) because a sibling link's
            # failure cancels other in-flight concurrent links via
            # AsyncParallelProcessor's cleanup — those cancelled links must
            # still get a matching completion event.
            if parameters.on_resource_type_completed:
                failed_resource_types = sorted({t.type_ for t in row.target if t.type_}) if row.target else []
                await parameters.on_resource_type_completed(
                    ResourceTypeCompletionEvent(
                        resource_types=failed_resource_types,
                        resource_count=0,
                        graph_depth=parameters.graph_depth,
                        urls=[],
                        link_index=context.task_index,
                        client_person_id=parameters.client_person_id,
                        connection_name=parameters.connection_name,
                    )
                )
            raise
```

with:

```python
        except asyncio.CancelledError:
            # Fire a matching completion event (if registered) before letting
            # the cancellation propagate, so a caller that already received
            # on_resource_type_started for this link doesn't get stuck
            # waiting forever for a completion event that will never come.
            # This is purely an additional signal — the cancellation is not
            # suppressed. Caught explicitly (it is a BaseException, not an
            # Exception) because a sibling link's failure cancels other
            # in-flight concurrent links via AsyncParallelProcessor's
            # cleanup — those cancelled links must still get a matching
            # completion event. Never classified as outcome="error" —
            # cancellation means "shut down", not "this resource type
            # failed" (see GraphRetrievalCompletedEvent.total_error_count's
            # docstring).
            if parameters.on_resource_type_completed:
                failed_resource_types = sorted({t.type_ for t in row.target if t.type_}) if row.target else []
                await parameters.on_resource_type_completed(
                    ResourceTypeCompletionEvent(
                        resource_types=failed_resource_types,
                        resource_count=0,
                        graph_depth=parameters.graph_depth,
                        urls=[],
                        link_index=context.task_index,
                        client_person_id=parameters.client_person_id,
                        connection_name=parameters.connection_name,
                        outcome="empty",
                        error_type=None,
                        error_message=None,
                    )
                )
            raise
        except Exception as exc:
            # Same reasoning as the CancelledError branch above, but for a
            # real fetch failure: fire the matching completion event with
            # outcome="error" before letting the exception propagate.
            if parameters.on_resource_type_completed:
                failed_resource_types = sorted({t.type_ for t in row.target if t.type_}) if row.target else []
                await parameters.on_resource_type_completed(
                    ResourceTypeCompletionEvent(
                        resource_types=failed_resource_types,
                        resource_count=0,
                        graph_depth=parameters.graph_depth,
                        urls=[],
                        link_index=context.task_index,
                        client_person_id=parameters.client_person_id,
                        connection_name=parameters.connection_name,
                        outcome="error",
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                )
            raise
```

- [ ] **Step 6: Update the start-resource fetch's exception handler**

In `_process_simulate_graph_by_resource_type_async`, replace:

```python
                except (Exception, asyncio.CancelledError, GeneratorExit):
                    # Fire a matching completion event (if registered) before
                    # letting the exception propagate, so the
                    # on_resource_type_started fired above for the start
                    # resource isn't left without a matching completion
                    # event. This is purely an additional signal — the
                    # exception is not suppressed. asyncio.CancelledError and
                    # GeneratorExit are caught explicitly (both are
                    # BaseException, not Exception) because a caller closing
                    # or abandoning this generator while the start-resource
                    # fetch is in flight raises GeneratorExit here, and a
                    # cancelled surrounding task raises CancelledError.
                    if on_resource_type_completed:
                        await on_resource_type_completed(
                            ResourceTypeCompletionEvent(
                                resource_types=[start],
                                resource_count=0,
                                graph_depth=0,
                                urls=[],
                                link_index=-1,
                                client_person_id=client_person_id,
                                connection_name=connection_name,
                            )
                        )
                    raise
```

with:

```python
                except (Exception, asyncio.CancelledError, GeneratorExit) as exc:
                    # Fire a matching completion event (if registered) before
                    # letting the exception propagate, so the
                    # on_resource_type_started fired above for the start
                    # resource isn't left without a matching completion
                    # event. This is purely an additional signal — the
                    # exception is not suppressed. asyncio.CancelledError and
                    # GeneratorExit are caught explicitly (both are
                    # BaseException, not Exception) because a caller closing
                    # or abandoning this generator while the start-resource
                    # fetch is in flight raises GeneratorExit here, and a
                    # cancelled surrounding task raises CancelledError.
                    # Cancellation/close is never classified as outcome=
                    # "error" or counted in total_error_count — see
                    # GraphRetrievalCompletedEvent.total_error_count's
                    # docstring. The start resource's own fetch failure is
                    # always fatal (this always re-raises), in every mode —
                    # there are no links to traverse without it.
                    is_real_error = isinstance(exc, Exception)
                    if is_real_error:
                        total_error_count += 1
                    if on_resource_type_completed:
                        await on_resource_type_completed(
                            ResourceTypeCompletionEvent(
                                resource_types=[start],
                                resource_count=0,
                                graph_depth=0,
                                urls=[],
                                link_index=-1,
                                client_person_id=client_person_id,
                                connection_name=connection_name,
                                outcome="error" if is_real_error else "empty",
                                error_type=type(exc).__name__ if is_real_error else None,
                                error_message=str(exc) if is_real_error else None,
                            )
                        )
                    raise
```

- [ ] **Step 7: Update the two remaining start-resource `ResourceTypeCompletionEvent` construction sites**

In the same method, replace:

```python
                parent_response_resource_count = parent_response.get_resource_count()
                if parent_response_resource_count == 0:
                    yield parent_response
                    if on_resource_type_completed:
                        # No resources came back for the start resource either —
                        # report it (declared type == start, the only type there
                        # ever is for the start resource) with resource_count=0 so
                        # the ResourceTypeStartedEvent fired above always has a
                        # matching completion event.
                        await on_resource_type_completed(
                            ResourceTypeCompletionEvent(
                                resource_types=[start],
                                resource_count=0,
                                graph_depth=0,
                                urls=[parent_queried_url] if parent_queried_url else [],
                                link_index=-1,
                                client_person_id=client_person_id,
                                connection_name=connection_name,
                            )
                        )
                    return
```

with:

```python
                parent_response_resource_count = parent_response.get_resource_count()
                if parent_response_resource_count == 0:
                    yield parent_response
                    if on_resource_type_completed:
                        # No resources came back for the start resource either —
                        # report it (declared type == start, the only type there
                        # ever is for the start resource) with resource_count=0 so
                        # the ResourceTypeStartedEvent fired above always has a
                        # matching completion event.
                        await on_resource_type_completed(
                            ResourceTypeCompletionEvent(
                                resource_types=[start],
                                resource_count=0,
                                graph_depth=0,
                                urls=[parent_queried_url] if parent_queried_url else [],
                                link_index=-1,
                                client_person_id=client_person_id,
                                connection_name=connection_name,
                                outcome="not_found" if parent_response.status == 404 else "empty",
                                error_type=None,
                                error_message=None,
                            )
                        )
                    return
```

and replace:

```python
                if on_resource_type_completed:
                    await on_resource_type_completed(
                        ResourceTypeCompletionEvent(
                            resource_types=[start],
                            resource_count=parent_response_resource_count,
                            graph_depth=0,
                            urls=[parent_queried_url] if parent_queried_url else [],
                            link_index=-1,
                            client_person_id=client_person_id,
                            connection_name=connection_name,
                        )
                    )
```

with:

```python
                if on_resource_type_completed:
                    await on_resource_type_completed(
                        ResourceTypeCompletionEvent(
                            resource_types=[start],
                            resource_count=parent_response_resource_count,
                            graph_depth=0,
                            urls=[parent_queried_url] if parent_queried_url else [],
                            link_index=-1,
                            client_person_id=client_person_id,
                            connection_name=connection_name,
                            outcome="success",
                            error_type=None,
                            error_message=None,
                        )
                    )
```

- [ ] **Step 8: Add `total_error_count`/`total_rejected_count` locals and wire them through the link-processing loop**

In the same method, replace:

```python
        all_resource_types: set[str] = set()
        total_resource_count: int = 0
        max_graph_depth: int = 0
        all_urls: set[str] = set()
```

with:

```python
        all_resource_types: set[str] = set()
        total_resource_count: int = 0
        max_graph_depth: int = 0
        all_urls: set[str] = set()
        total_error_count: int = 0
        total_rejected_count: int = 0
```

Then replace the link-processing `for links, current_parent_bundle_entries in parent_link_map:` block (the whole `async for context, link_responses in AsyncParallelProcessor(...)` loop and its body) with:

```python
                    for links, current_parent_bundle_entries in parent_link_map:
                        context: ParallelFunctionContext
                        link_responses: list[FhirGetResponse]
                        try:
                            async for context, link_responses in AsyncParallelProcessor(  # type: ignore[assignment]
                                name="process_link_async_parallel_function",
                                max_concurrent_tasks=max_concurrent_tasks,
                            ).process_rows_in_parallel(
                                rows=links,
                                process_row_fn=self.process_link_async_parallel_function,
                                parameters=GraphLinkParameters(
                                    parent_bundle_entries=current_parent_bundle_entries,
                                    logger=logger,
                                    cache=cache,
                                    scope_parser=scope_parser,
                                    max_concurrent_tasks=max_concurrent_tasks,
                                    on_resource_type_started=on_resource_type_started,
                                    on_resource_type_completed=on_resource_type_completed,
                                    graph_depth=graph_depth,
                                    url=base_url_value,
                                    client_person_id=client_person_id,
                                    connection_name=connection_name,
                                ),
                                log_level=self._log_level,
                                yield_context=True,
                                parent_link_map=new_parent_link_map,
                                request_size=request_size,
                                id_search_unsupported_resources=id_search_unsupported_resources,
                                add_cached_bundles_to_result=add_cached_bundles_to_result,
                                ifModifiedSince=ifModifiedSince,
                            ):
                                # Capture each response's actual queried URL before the
                                # existing loop below overwrites it with the base URL,
                                # filtering out empty strings (scope-denied / fully
                                # cached responses have url == "").
                                link_queried_urls = [r.url for r in link_responses if r.url]

                                # Yield each link's responses individually instead of accumulating
                                for link_response in link_responses:
                                    link_response.url = url or link_response.url
                                    yield link_response

                                resource_types = sorted({r.resource_type for r in link_responses if r.resource_type})
                                resource_count_for_link = sum(r.get_resource_count() for r in link_responses)

                                # The whole-graph aggregation only reflects resources
                                # actually retrieved — it must NOT be affected by the
                                # declared-type fallback used below for the
                                # per-link completion event.
                                if resource_types:
                                    all_resource_types.update(resource_types)
                                    total_resource_count += resource_count_for_link
                                    max_graph_depth = graph_depth
                                all_urls.update(link_queried_urls)

                                outcome = await self._fire_on_resource_type_completed_for_link(
                                    links=links,
                                    context=context,
                                    resource_types=resource_types,
                                    resource_count_for_link=resource_count_for_link,
                                    link_queried_urls=link_queried_urls,
                                    link_responses=link_responses,
                                    scope_parser=scope_parser,
                                    graph_depth=graph_depth,
                                    on_resource_type_completed=on_resource_type_completed,
                                    client_person_id=client_person_id,
                                    connection_name=connection_name,
                                )
                                if outcome == "scope_denied":
                                    total_rejected_count += 1
                        except Exception:
                            # A link's own fetch failure already fired its
                            # matching on_resource_type_completed
                            # (outcome="error") from inside
                            # process_link_async_parallel_function's except
                            # block before re-raising here. Count it before
                            # letting it continue propagating so the
                            # graph-level rollup reflects the failure that
                            # is about to abort this traversal, not just
                            # failures counted earlier in the same call.
                            # asyncio.CancelledError/GeneratorExit are never
                            # counted here (this only catches Exception).
                            total_error_count += 1
                            raise
```

- [ ] **Step 9: Wire the rollups into the final `GraphRetrievalCompletedEvent`**

In the same method, replace:

```python
                if on_graph_retrieval_completed:
                    await on_graph_retrieval_completed(
                        GraphRetrievalCompletedEvent(
                            resource_types=sorted(all_resource_types),
                            total_resource_count=total_resource_count,
                            max_graph_depth=max_graph_depth,
                            urls=sorted(all_urls),
                            client_person_id=client_person_id,
                            connection_name=connection_name,
                        )
```

with:

```python
                if on_graph_retrieval_completed:
                    await on_graph_retrieval_completed(
                        GraphRetrievalCompletedEvent(
                            resource_types=sorted(all_resource_types),
                            total_resource_count=total_resource_count,
                            max_graph_depth=max_graph_depth,
                            urls=sorted(all_urls),
                            client_person_id=client_person_id,
                            connection_name=connection_name,
                            total_error_count=total_error_count,
                            total_rejected_count=total_rejected_count,
                        )
```

(the closing `)` and `)` on the following line are unchanged — this only adds two keyword arguments inside the existing call).

- [ ] **Step 10: Run the targeted tests**

Run: `uv run pytest helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py -v`
Expected: PASS (all tests, including the new ones from Step 1)

- [ ] **Step 11: Run the full graph + async-parallel-processor suite and mypy**

Run: `uv run pytest helix_fhir_client_sdk/graph/test/ helix_fhir_client_sdk/utilities/async_parallel_processor/v1/test/ -v`
Expected: PASS

Run: `uv run mypy helix_fhir_client_sdk/`
Expected: `Success: no issues found`

- [ ] **Step 12: Commit**

```bash
git add helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py
git commit -m "DCON-5229 classify outcome (success/empty/not_found/scope_denied/error) on every fired ResourceTypeCompletionEvent"
```

---

## Task 4: Add opt-in `continue_on_resource_type_error`

**Files:**
- Modify: `helix_fhir_client_sdk/graph/graph_link_parameters.py`
- Modify: `helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py`
- Modify: `helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py`

**Interfaces:**
- Consumes: `_fire_on_resource_type_completed_for_link(..., error: Exception | None = None)` (Task 3) — this task starts passing a real value.
- Produces: `GraphLinkParameters.continue_on_resource_type_error: bool = False`; `SimulatedGraphProcessorMixin.simulate_graph_by_resource_type_async(..., continue_on_resource_type_error: bool = False)`; a new private module-level dataclass `_LinkFetchResult` in `simulated_graph_processor_mixin.py` with fields `responses: list[FhirGetResponse]` and `error: Exception | None = None` — the new return type of `process_link_async_parallel_function` (previously `list[FhirGetResponse]`).

- [ ] **Step 1: Write the failing tests**

Add these tests to the end of `helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py`:

```python
@pytest.mark.asyncio
async def test_continue_on_resource_type_error_false_still_aborts() -> None:
    # Default (False) must behave exactly as before this feature existed —
    # a link's fetch failure still aborts the whole traversal.
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    responses: list[Any] = []

    with aioresponses() as m:
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Patient", "id": "1"},
        )
        m.get(
            "http://example.com/fhir/AllergyIntolerance?patient=1",
            exception=RuntimeError("simulated network failure fetching link"),
        )
        m.get(
            "http://example.com/fhir/CarePlan?patient=1",
            payload={"resourceType": "CarePlan", "id": "1"},
        )

        with pytest.raises(FhirSenderException):
            async for r in graph_processor.simulate_graph_by_resource_type_async(
                id_="1",
                graph_json=TWO_LINK_GRAPH,
                contained=False,
                max_concurrent_tasks=1,
                continue_on_resource_type_error=False,
            ):
                responses.append(r)

    # Only the start resource (Patient) was yielded before the abort —
    # CarePlan, sequenced after the failing AllergyIntolerance link at
    # max_concurrent_tasks=1, never got a chance to run.
    assert len(responses) == 1
    assert responses[0].resource_type == "Patient"


@pytest.mark.asyncio
async def test_continue_on_resource_type_error_true_continues_past_failure() -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    completed_events: list[ResourceTypeCompletionEvent] = []
    graph_completed_events: list[GraphRetrievalCompletedEvent] = []

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    async def on_graph_completed(event: GraphRetrievalCompletedEvent) -> None:
        graph_completed_events.append(event)

    with aioresponses() as m:
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Patient", "id": "1"},
        )
        m.get(
            "http://example.com/fhir/AllergyIntolerance?patient=1",
            exception=RuntimeError("simulated network failure fetching link"),
        )
        m.get(
            "http://example.com/fhir/CarePlan?patient=1",
            payload={"resourceType": "CarePlan", "id": "1"},
        )

        responses = [
            r
            async for r in graph_processor.simulate_graph_by_resource_type_async(
                id_="1",
                graph_json=TWO_LINK_GRAPH,
                contained=False,
                max_concurrent_tasks=1,
                continue_on_resource_type_error=True,
                on_resource_type_completed=on_completed,
                on_graph_retrieval_completed=on_graph_completed,
            )
        ]

    # Patient and CarePlan both came through despite AllergyIntolerance's
    # fetch failing — the traversal did not abort.
    assert sorted(r.resource_type for r in responses) == ["CarePlan", "Patient"]

    allergy_completed = [e for e in completed_events if e.resource_types == ["AllergyIntolerance"]]
    assert len(allergy_completed) == 1
    assert allergy_completed[0].outcome == "error"
    assert allergy_completed[0].error_type == "FhirSenderException"

    care_plan_completed = [e for e in completed_events if e.resource_types == ["CarePlan"]]
    assert len(care_plan_completed) == 1
    assert care_plan_completed[0].outcome == "success"

    assert len(graph_completed_events) == 1
    assert graph_completed_events[0].total_error_count == 1
    assert sorted(graph_completed_events[0].resource_types) == ["CarePlan", "Patient"]


@pytest.mark.asyncio
async def test_continue_on_resource_type_error_true_start_resource_still_fatal() -> None:
    # The start resource's own fetch failure is always fatal, in every
    # mode — there are no links to traverse without it.
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    with aioresponses() as m:
        m.get(
            "http://example.com/fhir/Patient/1",
            exception=RuntimeError("simulated network failure fetching start resource"),
        )

        with pytest.raises(FhirSenderException):
            async for _ in graph_processor.simulate_graph_by_resource_type_async(
                id_="1",
                graph_json=TWO_LINK_GRAPH,
                contained=False,
                max_concurrent_tasks=1,
                continue_on_resource_type_error=True,
            ):
                pass


@pytest.mark.asyncio
async def test_continue_on_resource_type_error_true_cancellation_still_propagates() -> None:
    # asyncio.CancelledError must never be swallowed as a "continue past
    # this error" case, in either mode — cancellation means shut down, not
    # "this resource type failed".
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    async def raise_cancelled(**kwargs: Any) -> AsyncGenerator[Any, None]:
        raise asyncio.CancelledError()
        yield  # pragma: no cover - unreachable; makes this an async generator function

    graph_processor._process_link_async = raise_cancelled  # type: ignore[method-assign]

    with aioresponses() as m:
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Patient", "id": "1"},
        )

        with pytest.raises(asyncio.CancelledError):
            async for _ in graph_processor.simulate_graph_by_resource_type_async(
                id_="1",
                graph_json=TWO_LINK_GRAPH,
                contained=False,
                max_concurrent_tasks=1,
                continue_on_resource_type_error=True,
            ):
                pass


@pytest.mark.asyncio
async def test_continue_on_resource_type_error_true_skips_failed_links_nested_children() -> None:
    # A failed link's own nested target.link children never run — there is
    # no parent bundle to traverse from since the fetch that would have
    # produced it failed.
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    started_events: list[ResourceTypeStartedEvent] = []

    async def on_started(event: ResourceTypeStartedEvent) -> None:
        started_events.append(event)

    with aioresponses() as m:
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Patient", "id": "1"},
        )
        m.get(
            "http://example.com/fhir/Encounter?patient=1",
            exception=RuntimeError("simulated network failure fetching Encounter"),
        )

        async for _ in graph_processor.simulate_graph_by_resource_type_async(
            id_="1",
            graph_json=NESTED_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
            continue_on_resource_type_error=True,
            on_resource_type_started=on_started,
        ):
            pass

    # Only Patient (link_index=-1) and Encounter (link_index=0, graph_depth=0)
    # ever started — Practitioner (nested under Encounter's target.link) never
    # got a started event, since Encounter's own fetch failed before it could
    # produce any parent bundle entries for Practitioner to traverse from.
    assert {e.resource_types[0] if e.resource_types else "" for e in started_events} <= {"Patient", "Encounter"}
    assert not any("Practitioner" in e.resource_types for e in started_events)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py -v -k "continue_on_resource_type_error"`
Expected: FAIL — `TypeError: simulate_graph_by_resource_type_async() got an unexpected keyword argument 'continue_on_resource_type_error'`

- [ ] **Step 3: Add the field to `GraphLinkParameters`**

In `helix_fhir_client_sdk/graph/graph_link_parameters.py`, add this field at the end of the class (after the existing `connection_name` field and its docstring):

```python
    continue_on_resource_type_error: bool = False
    """When True, a link's own fetch failure fires on_resource_type_completed
    with outcome="error" and the traversal continues to the next link
    instead of re-raising. Defaults to False, which preserves this SDK's
    original behavior exactly (fire the completion event, then re-raise,
    aborting the traversal) — existing callers that don't pass this on
    simulate_graph_by_resource_type_async() see zero behavior change. Not
    consulted by simulate_graph_async() (the non-streaming sibling method),
    which never sets it and so always gets the default False."""
```

- [ ] **Step 4: Add the `_LinkFetchResult` container and update `process_link_async_parallel_function`**

In `helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py`, add this dataclass immediately before the `class SimulatedGraphProcessorMixin(ABC, FhirClientProtocol):` line (so right after the existing imports, before the class definition):

```python
@dataclass(slots=True)
class _LinkFetchResult:
    """
    Return shape for process_link_async_parallel_function. `error` is set
    only when the link's own fetch raised a real Exception (never
    asyncio.CancelledError — that always propagates immediately instead)
    AND the caller opted into continue_on_resource_type_error, so the
    consumer loop in _process_simulate_graph_by_resource_type_async can
    classify and fire the matching completion event itself (with
    outcome="error") instead of process_link_async_parallel_function firing
    it and re-raising. Not part of this SDK's public API.
    """

    responses: list[FhirGetResponse]
    error: Exception | None = None
```

Add the `dataclass` import at the top of the same file — change:

```python
from datetime import UTC, datetime
```

to:

```python
from dataclasses import dataclass
from datetime import UTC, datetime
```

Then, in `process_link_async_parallel_function`, change the return type annotation from:

```python
    ) -> list[FhirGetResponse]:
```

to (this is the method's own signature, the first one in the file — do not change `_process_link_async`'s or `_process_child_group`'s return types, only this one):

```python
    ) -> _LinkFetchResult:
```

Replace the method's final line:

```python
        # Return the list of retrieved responses
        return result
```

with:

```python
        # Return the list of retrieved responses
        return _LinkFetchResult(responses=result)
```

Replace the two except clauses added in Task 3 with:

```python
        except asyncio.CancelledError:
            # Fire a matching completion event (if registered) before letting
            # the cancellation propagate, so a caller that already received
            # on_resource_type_started for this link doesn't get stuck
            # waiting forever for a completion event that will never come.
            # This is purely an additional signal — the cancellation is not
            # suppressed. Caught explicitly (it is a BaseException, not an
            # Exception) because a sibling link's failure cancels other
            # in-flight concurrent links via AsyncParallelProcessor's
            # cleanup — those cancelled links must still get a matching
            # completion event. Never classified as outcome="error", and
            # never subject to continue_on_resource_type_error — cancellation
            # means "shut down", not "this resource type failed", in either
            # mode (see GraphRetrievalCompletedEvent.total_error_count's
            # docstring).
            if parameters.on_resource_type_completed:
                failed_resource_types = sorted({t.type_ for t in row.target if t.type_}) if row.target else []
                await parameters.on_resource_type_completed(
                    ResourceTypeCompletionEvent(
                        resource_types=failed_resource_types,
                        resource_count=0,
                        graph_depth=parameters.graph_depth,
                        urls=[],
                        link_index=context.task_index,
                        client_person_id=parameters.client_person_id,
                        connection_name=parameters.connection_name,
                        outcome="empty",
                        error_type=None,
                        error_message=None,
                    )
                )
            raise
        except Exception as exc:
            if parameters.continue_on_resource_type_error:
                # Defer firing the completion event to the consumer loop in
                # _process_simulate_graph_by_resource_type_async, which
                # classifies outcome="error" from this returned error and
                # fires exactly one completion event for this link — firing
                # here too would double-fire it.
                return _LinkFetchResult(responses=[], error=exc)

            # Default behavior (continue_on_resource_type_error=False):
            # fire the matching completion event before letting the
            # exception propagate, exactly as before this flag existed.
            if parameters.on_resource_type_completed:
                failed_resource_types = sorted({t.type_ for t in row.target if t.type_}) if row.target else []
                await parameters.on_resource_type_completed(
                    ResourceTypeCompletionEvent(
                        resource_types=failed_resource_types,
                        resource_count=0,
                        graph_depth=parameters.graph_depth,
                        urls=[],
                        link_index=context.task_index,
                        client_person_id=parameters.client_person_id,
                        connection_name=parameters.connection_name,
                        outcome="error",
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                )
            raise
```

- [ ] **Step 5: Fix `process_simulate_graph_async`'s call site for the changed return type**

`process_link_async_parallel_function` is also used by `process_simulate_graph_async` (the older, non-streaming, accumulating method — it never sets `continue_on_resource_type_error`, so it always gets the default `False` and only ever receives the success shape). In `process_simulate_graph_async`, replace:

```python
                    async for link_responses in AsyncParallelProcessor(
                        name="process_link_async_parallel_function",
                        max_concurrent_tasks=max_concurrent_tasks,
                    ).process_rows_in_parallel(
                        rows=link,
                        process_row_fn=self.process_link_async_parallel_function,
                        parameters=GraphLinkParameters(
                            parent_bundle_entries=parent_bundle_entries,
                            logger=logger,
                            cache=cache,
                            scope_parser=scope_parser,
                            max_concurrent_tasks=max_concurrent_tasks,
                        ),
                        log_level=self._log_level,
                        parent_link_map=new_parent_link_map,
                        request_size=request_size,
                        id_search_unsupported_resources=id_search_unsupported_resources,
                        add_cached_bundles_to_result=add_cached_bundles_to_result,
                        ifModifiedSince=ifModifiedSince,
                    ):
                        child_responses.extend(link_responses)
```

with:

```python
                    async for link_fetch_result in AsyncParallelProcessor(
                        name="process_link_async_parallel_function",
                        max_concurrent_tasks=max_concurrent_tasks,
                    ).process_rows_in_parallel(
                        rows=link,
                        process_row_fn=self.process_link_async_parallel_function,
                        parameters=GraphLinkParameters(
                            parent_bundle_entries=parent_bundle_entries,
                            logger=logger,
                            cache=cache,
                            scope_parser=scope_parser,
                            max_concurrent_tasks=max_concurrent_tasks,
                        ),
                        log_level=self._log_level,
                        parent_link_map=new_parent_link_map,
                        request_size=request_size,
                        id_search_unsupported_resources=id_search_unsupported_resources,
                        add_cached_bundles_to_result=add_cached_bundles_to_result,
                        ifModifiedSince=ifModifiedSince,
                    ):
                        child_responses.extend(link_fetch_result.responses)
```

(the type annotation line just above this loop, `link_responses: list[FhirGetResponse]`, must be deleted since the loop variable is renamed and no longer needs — nor matches — that annotation.)

- [ ] **Step 6: Add the parameter to `_process_simulate_graph_by_resource_type_async`'s signature**

Replace:

```python
        on_resource_type_completed: (Callable[[ResourceTypeCompletionEvent], Awaitable[None]] | None) = None,
        on_resource_type_started: (Callable[[ResourceTypeStartedEvent], Awaitable[None]] | None) = None,
        on_graph_retrieval_started: (Callable[[GraphRetrievalStartedEvent], Awaitable[None]] | None) = None,
        on_graph_retrieval_completed: (Callable[[GraphRetrievalCompletedEvent], Awaitable[None]] | None) = None,
        client_person_id: str = "",
        connection_name: str = "",
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        Core implementation that yields per graph link instead of accumulating all responses.
        Each yield contains the resources for one link traversal (typically one resource type).
        """
```

with:

```python
        on_resource_type_completed: (Callable[[ResourceTypeCompletionEvent], Awaitable[None]] | None) = None,
        on_resource_type_started: (Callable[[ResourceTypeStartedEvent], Awaitable[None]] | None) = None,
        on_graph_retrieval_started: (Callable[[GraphRetrievalStartedEvent], Awaitable[None]] | None) = None,
        on_graph_retrieval_completed: (Callable[[GraphRetrievalCompletedEvent], Awaitable[None]] | None) = None,
        client_person_id: str = "",
        connection_name: str = "",
        continue_on_resource_type_error: bool = False,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        Core implementation that yields per graph link instead of accumulating all responses.
        Each yield contains the resources for one link traversal (typically one resource type).
        """
```

- [ ] **Step 7: Add the parameter to the public `simulate_graph_by_resource_type_async` method and thread it through**

In the public `simulate_graph_by_resource_type_async` method, replace:

```python
        on_resource_type_completed: (Callable[[ResourceTypeCompletionEvent], Awaitable[None]] | None) = None,
        on_resource_type_started: (Callable[[ResourceTypeStartedEvent], Awaitable[None]] | None) = None,
        on_graph_retrieval_started: (Callable[[GraphRetrievalStartedEvent], Awaitable[None]] | None) = None,
        on_graph_retrieval_completed: (Callable[[GraphRetrievalCompletedEvent], Awaitable[None]] | None) = None,
        client_person_id: str = "",
        connection_name: str = "",
    ) -> AsyncGenerator[FhirGetResponse, None]:
```

with:

```python
        on_resource_type_completed: (Callable[[ResourceTypeCompletionEvent], Awaitable[None]] | None) = None,
        on_resource_type_started: (Callable[[ResourceTypeStartedEvent], Awaitable[None]] | None) = None,
        on_graph_retrieval_started: (Callable[[GraphRetrievalStartedEvent], Awaitable[None]] | None) = None,
        on_graph_retrieval_completed: (Callable[[GraphRetrievalCompletedEvent], Awaitable[None]] | None) = None,
        client_person_id: str = "",
        connection_name: str = "",
        continue_on_resource_type_error: bool = False,
    ) -> AsyncGenerator[FhirGetResponse, None]:
```

Add this line to that method's docstring, immediately after the existing `:param connection_name:` entry:

```python
        :param continue_on_resource_type_error: Optional flag (default False,
                                                   preserving today's exact
                                                   behavior). When True, a
                                                   link's own fetch failure
                                                   fires on_resource_type_completed
                                                   with outcome="error" and the
                                                   traversal continues to the
                                                   next link instead of
                                                   re-raising. The start
                                                   resource's own fetch
                                                   failure is always fatal,
                                                   regardless of this flag.
```

Then, in the same method's body, replace:

```python
        inner_generator = self._process_simulate_graph_by_resource_type_async(
            id_=id_,
            graph_json=graph_json,
            contained=contained,
            separate_bundle_resources=separate_bundle_resources,
            restrict_to_scope=restrict_to_scope,
            restrict_to_resources=restrict_to_resources,
            restrict_to_capability_statement=restrict_to_capability_statement,
            retrieve_and_restrict_to_capability_statement=retrieve_and_restrict_to_capability_statement,
            ifModifiedSince=ifModifiedSince,
            eTag=eTag,
            url=self._url,
            expand_fhir_bundle=self._expand_fhir_bundle,
            logger=self._logger,
            auth_scopes=self._auth_scopes,
            request_size=request_size,
            max_concurrent_tasks=max_concurrent_tasks,
            sort_resources=sort_resources,
            add_cached_bundles_to_result=add_cached_bundles_to_result,
            input_cache=input_cache,
            compare_hash=compare_hash,
            on_resource_type_completed=on_resource_type_completed,
            on_resource_type_started=on_resource_type_started,
            on_graph_retrieval_started=on_graph_retrieval_started,
            on_graph_retrieval_completed=on_graph_retrieval_completed,
            client_person_id=client_person_id,
            connection_name=connection_name,
        )
```

with:

```python
        inner_generator = self._process_simulate_graph_by_resource_type_async(
            id_=id_,
            graph_json=graph_json,
            contained=contained,
            separate_bundle_resources=separate_bundle_resources,
            restrict_to_scope=restrict_to_scope,
            restrict_to_resources=restrict_to_resources,
            restrict_to_capability_statement=restrict_to_capability_statement,
            retrieve_and_restrict_to_capability_statement=retrieve_and_restrict_to_capability_statement,
            ifModifiedSince=ifModifiedSince,
            eTag=eTag,
            url=self._url,
            expand_fhir_bundle=self._expand_fhir_bundle,
            logger=self._logger,
            auth_scopes=self._auth_scopes,
            request_size=request_size,
            max_concurrent_tasks=max_concurrent_tasks,
            sort_resources=sort_resources,
            add_cached_bundles_to_result=add_cached_bundles_to_result,
            input_cache=input_cache,
            compare_hash=compare_hash,
            on_resource_type_completed=on_resource_type_completed,
            on_resource_type_started=on_resource_type_started,
            on_graph_retrieval_started=on_graph_retrieval_started,
            on_graph_retrieval_completed=on_graph_retrieval_completed,
            client_person_id=client_person_id,
            connection_name=connection_name,
            continue_on_resource_type_error=continue_on_resource_type_error,
        )
```

- [ ] **Step 8: Update the consumer loop in `_process_simulate_graph_by_resource_type_async` to unwrap `_LinkFetchResult` and pass `error` through**

Replace:

```python
                            async for context, link_responses in AsyncParallelProcessor(  # type: ignore[assignment]
                                name="process_link_async_parallel_function",
                                max_concurrent_tasks=max_concurrent_tasks,
                            ).process_rows_in_parallel(
                                rows=links,
                                process_row_fn=self.process_link_async_parallel_function,
                                parameters=GraphLinkParameters(
                                    parent_bundle_entries=current_parent_bundle_entries,
                                    logger=logger,
                                    cache=cache,
                                    scope_parser=scope_parser,
                                    max_concurrent_tasks=max_concurrent_tasks,
                                    on_resource_type_started=on_resource_type_started,
                                    on_resource_type_completed=on_resource_type_completed,
                                    graph_depth=graph_depth,
                                    url=base_url_value,
                                    client_person_id=client_person_id,
                                    connection_name=connection_name,
                                ),
                                log_level=self._log_level,
                                yield_context=True,
                                parent_link_map=new_parent_link_map,
                                request_size=request_size,
                                id_search_unsupported_resources=id_search_unsupported_resources,
                                add_cached_bundles_to_result=add_cached_bundles_to_result,
                                ifModifiedSince=ifModifiedSince,
                            ):
                                # Capture each response's actual queried URL before the
                                # existing loop below overwrites it with the base URL,
                                # filtering out empty strings (scope-denied / fully
                                # cached responses have url == "").
                                link_queried_urls = [r.url for r in link_responses if r.url]

                                # Yield each link's responses individually instead of accumulating
                                for link_response in link_responses:
                                    link_response.url = url or link_response.url
                                    yield link_response

                                resource_types = sorted({r.resource_type for r in link_responses if r.resource_type})
                                resource_count_for_link = sum(r.get_resource_count() for r in link_responses)

                                # The whole-graph aggregation only reflects resources
                                # actually retrieved — it must NOT be affected by the
                                # declared-type fallback used below for the
                                # per-link completion event.
                                if resource_types:
                                    all_resource_types.update(resource_types)
                                    total_resource_count += resource_count_for_link
                                    max_graph_depth = graph_depth
                                all_urls.update(link_queried_urls)

                                outcome = await self._fire_on_resource_type_completed_for_link(
                                    links=links,
                                    context=context,
                                    resource_types=resource_types,
                                    resource_count_for_link=resource_count_for_link,
                                    link_queried_urls=link_queried_urls,
                                    link_responses=link_responses,
                                    scope_parser=scope_parser,
                                    graph_depth=graph_depth,
                                    on_resource_type_completed=on_resource_type_completed,
                                    client_person_id=client_person_id,
                                    connection_name=connection_name,
                                )
                                if outcome == "scope_denied":
                                    total_rejected_count += 1
```

with:

```python
                            async for context, link_fetch_result in AsyncParallelProcessor(  # type: ignore[assignment]
                                name="process_link_async_parallel_function",
                                max_concurrent_tasks=max_concurrent_tasks,
                            ).process_rows_in_parallel(
                                rows=links,
                                process_row_fn=self.process_link_async_parallel_function,
                                parameters=GraphLinkParameters(
                                    parent_bundle_entries=current_parent_bundle_entries,
                                    logger=logger,
                                    cache=cache,
                                    scope_parser=scope_parser,
                                    max_concurrent_tasks=max_concurrent_tasks,
                                    on_resource_type_started=on_resource_type_started,
                                    on_resource_type_completed=on_resource_type_completed,
                                    graph_depth=graph_depth,
                                    url=base_url_value,
                                    client_person_id=client_person_id,
                                    connection_name=connection_name,
                                    continue_on_resource_type_error=continue_on_resource_type_error,
                                ),
                                log_level=self._log_level,
                                yield_context=True,
                                parent_link_map=new_parent_link_map,
                                request_size=request_size,
                                id_search_unsupported_resources=id_search_unsupported_resources,
                                add_cached_bundles_to_result=add_cached_bundles_to_result,
                                ifModifiedSince=ifModifiedSince,
                            ):
                                link_responses = link_fetch_result.responses

                                # Capture each response's actual queried URL before the
                                # existing loop below overwrites it with the base URL,
                                # filtering out empty strings (scope-denied / fully
                                # cached responses have url == "").
                                link_queried_urls = [r.url for r in link_responses if r.url]

                                # Yield each link's responses individually instead of accumulating
                                for link_response in link_responses:
                                    link_response.url = url or link_response.url
                                    yield link_response

                                resource_types = sorted({r.resource_type for r in link_responses if r.resource_type})
                                resource_count_for_link = sum(r.get_resource_count() for r in link_responses)

                                # The whole-graph aggregation only reflects resources
                                # actually retrieved — it must NOT be affected by the
                                # declared-type fallback used below for the
                                # per-link completion event.
                                if resource_types:
                                    all_resource_types.update(resource_types)
                                    total_resource_count += resource_count_for_link
                                    max_graph_depth = graph_depth
                                all_urls.update(link_queried_urls)

                                outcome = await self._fire_on_resource_type_completed_for_link(
                                    links=links,
                                    context=context,
                                    resource_types=resource_types,
                                    resource_count_for_link=resource_count_for_link,
                                    link_queried_urls=link_queried_urls,
                                    link_responses=link_responses,
                                    scope_parser=scope_parser,
                                    graph_depth=graph_depth,
                                    on_resource_type_completed=on_resource_type_completed,
                                    client_person_id=client_person_id,
                                    connection_name=connection_name,
                                    error=link_fetch_result.error,
                                )
                                if outcome == "error":
                                    total_error_count += 1
                                elif outcome == "scope_denied":
                                    total_rejected_count += 1
```

(note: the `except Exception: total_error_count += 1; raise` wrapper added around this `async for` in Task 3 is unchanged and still correct — it only ever triggers when `continue_on_resource_type_error` is `False`, or for a bug that lets some other exception past `process_link_async_parallel_function`'s own handling, since a `True`-mode link failure no longer raises out of this loop at all. `continue_on_resource_type_error` is now in scope here because Step 6 added it to this method's signature.)

- [ ] **Step 9: Run the targeted tests**

Run: `uv run pytest helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py -v`
Expected: PASS (all tests, including the 5 new ones from Step 1)

- [ ] **Step 10: Run mypy**

Run: `uv run mypy helix_fhir_client_sdk/`
Expected: `Success: no issues found`

- [ ] **Step 11: Commit**

```bash
git add helix_fhir_client_sdk/graph/graph_link_parameters.py helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py
git commit -m "DCON-5229 add opt-in continue_on_resource_type_error so a link failure no longer has to abort the whole traversal"
```

---

## Task 5: Full regression suite and final review

**Files:** None (verification only).

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest helix_fhir_client_sdk/ -v`
Expected: All tests pass (238+ tests from before this plan, plus the ~15 new tests added across Tasks 1-4).

- [ ] **Step 2: Run mypy across the whole package**

Run: `uv run mypy helix_fhir_client_sdk/`
Expected: `Success: no issues found`

- [ ] **Step 3: Run the pre-commit suite manually (ruff, bandit, secret detection) if not already run via the commit hooks in prior tasks**

Run: `uv run ruff check helix_fhir_client_sdk/` and `uv run ruff format --check helix_fhir_client_sdk/`
Expected: No findings (these already run automatically via this repo's pre-commit hook on every `git commit`, so this step is a dry-run sanity check, not a new gate).

- [ ] **Step 4: Update the design spec's Status line**

In `docs/superpowers/specs/2026-08-23-resource-type-error-visibility-design.md`, change:

```markdown
**Status:** Design approved, not yet implemented · **Ticket:** DCON-5229 (follow-on to the completion-hook feature; related to EA-2509) · **Repo:** `helix.fhir.client.sdk`
```

to:

```markdown
**Status:** Implemented · **Ticket:** DCON-5229 (follow-on to the completion-hook feature; related to EA-2509) · **Repo:** `helix.fhir.client.sdk`
```

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-08-23-resource-type-error-visibility-design.md
git commit -m "DCON-5229 mark error/rejection visibility design spec as implemented"
```

- [ ] **Step 6: Push**

```bash
git push origin iq-dcon-proa-phase2-completion-hook-plan
```

This updates PR #242 with the full error/rejection-visibility feature, on top of the already-pushed completion-hook feature and the two concurrency bug fixes.

---

## Execution notes (what actually happened)

Executed via `superpowers:subagent-driven-development` — one fresh implementer subagent per task, task-scoped review after each, final whole-branch review at the end. Deviations from this plan's literal text, and why:

- **Tasks 1, 2, and 3 landed in ONE commit (`548185c`), not three.** This repo's pre-commit hook always runs `mypy --strict` across the *entire* `helix_fhir_client_sdk/` package (`pre-commit.Dockerfile`'s `CMD ["pre-commit", "run", "--all-files"]`), regardless of what's staged. Tasks 1-2 alone leave the package inconsistent (new required dataclass fields with no consumer yet) until Task 3 lands, so committing after each would have been genuinely blocked by the hook — not a case for `--no-verify` (never used; that's a hard CLAUDE.md violation). Tasks 1 and 2 staged their changes instead of committing; Task 3 committed all three together once the whole repo was green again. Task 4 and Task 5 commit normally per the plan (each already leaves the repo internally consistent on its own).
- **Two real bugs found during Task 3's own implementation** (not transcription errors — the plan's literal Step 1 test and Step 4 classification code both had genuine gaps): the `scope_denied` test's brief text used a nonexistent public-method kwarg and a scope that also denied the start resource; and the outcome-classification precedence let a 404's `OperationOutcome` body (which counts as "1 resource") misclassify as `"success"` before the fallback-notfound check ever ran. Both fixed during Task 3's review fix-round; see commit `548185c`'s content for the final, correct code (this plan's literal Step 1/Step 4 text reflects the *original*, buggy intent — read the design spec's Decision 1 for the corrected precedence).
- **Final whole-branch review found one Critical regression and 3 Important gaps** this plan's task-scoped reviews structurally could not see: the start-resource classification (Step 7) had the identical `OperationOutcome`-counts-as-a-resource defect in a sibling code path, plus it used a whole-response `status`/`successful` flag that silently dropped real data for a partially-found multi-id fetch; non-404 HTTP errors that this SDK's retry client returns rather than raises for (400/403) were indistinguishable from "no data"; a loop-level exception wrapper miscounted a caller's own callback exceptions as fetch failures; and continue-mode failures had no log line. All four fixed in one consolidated fix-wave commit (`291dc19`), re-review-verified. See the design spec's Decision 1/Decision 3 (amended) for the corrected, final behavior — this plan's literal code snippets predate these fixes.

For the full task-by-task ledger (rulings, fix rounds, review verdicts), see the session that executed this plan — the SDD workspace ledger itself is git-ignored scratch space and was deleted after the final review passed, per that process's own cleanup step; this section is the durable summary.
