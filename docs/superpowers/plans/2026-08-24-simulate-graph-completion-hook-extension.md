# Extending the Completion-Hook Event Lifecycle to `simulate_graph_async()` and `simulate_graph_streaming_async()` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `simulate_graph_async()` and `simulate_graph_streaming_async()` the same event lifecycle (`on_graph_retrieval_started/completed`, `on_resource_type_started/completed`), outcome/error visibility, and `continue_on_resource_type_error` opt-in that `simulate_graph_by_resource_type_async()` already has — as a pure side channel, with zero behavior change for any caller that passes none of the new parameters.

**Architecture:** All three graph-retrieval methods in `helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py` share one traversal core, `process_simulate_graph_async()`. This plan extends that shared core with the same optional event/outcome machinery `_process_simulate_graph_by_resource_type_async()` already has, reusing the already-generic `_fire_on_resource_type_completed_for_link()` and `GraphLinkParameters`/`process_link_async_parallel_function()` machinery as-is (no changes needed there). `simulate_graph_async()` and `simulate_graph_streaming_async()` both gain the new keyword-only parameters and forward them straight through. No new files, no schema changes to any event dataclass.

**Tech Stack:** Python 3.13, dataclasses (`slots=True`), `asyncio`, `aioresponses` for HTTP-level test mocking, `pytest` + `pytest-asyncio`, `uv`, `mypy`, `ruff`.

**Spec:** `docs/superpowers/specs/2026-08-24-simulate-graph-completion-hook-extension-design.md`

## Global Constraints

- Ticket: TBD — every commit message in this plan uses the placeholder prefix `TICKET-TBD` for now; replace with the real JIRA key across all commits (`git commit --amend` / interactive rebase) before opening a PR, per this org's commit-message convention.
- Every new parameter defaults to `None`/`""`/`False` — a caller of `simulate_graph_async()` or `simulate_graph_streaming_async()` that passes none of them must see **zero behavior change** versus today. This is the single hardest requirement in this plan; the backward-compatibility tests in Task 1 exist specifically to prove it.
- `process_simulate_graph_async()`'s existing zero-vs-nonzero start-resource branching (`parent_response_resource_count == 0`, the *raw* `get_resource_count()`) is **not changed** by this plan — only `_process_simulate_graph_by_resource_type_async()` has the more careful content-based (`OperationOutcome`-excluding) branching check, and that stays exclusive to it. The event fired for the start resource must still report the *correct* `outcome` (e.g. `"not_found"` for a 404-with-body response) regardless of which branch the unchanged raw-count check takes — see Task 1, Step 7's commentary.
- `asyncio.CancelledError` is never treated as a resource-type error, in either mode — it always propagates immediately after firing its completion event. Do not regress this guarantee (already correct in `process_link_async_parallel_function()`, which is reused unchanged).
- The start resource's own fetch failure is always fatal, in every mode, for both methods.
- No changes to `_process_simulate_graph_by_resource_type_async()`, `simulate_graph_by_resource_type_async()`, `_fire_on_resource_type_completed_for_link()`, `process_link_async_parallel_function()`, or `GraphLinkParameters`' fields (only its docstrings change, in Task 2) — every one of those is reused exactly as it exists today.
- Tests live in `helix_fhir_client_sdk/graph/test/` — no pytest fixtures, just the existing `TestGraphProcessor(FhirClient)` / `get_graph_processor()` pattern (from `helix_fhir_client_sdk/graph/test/test_simulate_graph_processor_mixin.py`) and `aioresponses()` HTTP-level mocking.
- Run `uv run pytest helix_fhir_client_sdk/graph/test/ -v` and `uv run mypy helix_fhir_client_sdk/` after every task; run the full `uv run pytest helix_fhir_client_sdk/ -v` regression suite plus `uv run ruff check` / `uv run ruff format --check` before the final commit (Task 3).

---

## Task 1: Extend `process_simulate_graph_async()`, `simulate_graph_async()`, and `simulate_graph_streaming_async()` with the full event/outcome/continue-on-error API

**Files:**
- Modify: `helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py` (three methods: `process_simulate_graph_async` at line 92, `simulate_graph_async` at line 1266, `simulate_graph_streaming_async` at line 1345 — line numbers as of this plan's writing; re-locate by method name if they've shifted)
- Create: `helix_fhir_client_sdk/graph/test/test_simulate_graph_async_and_streaming_completion_hook.py`

**Interfaces:**
- Consumes (unchanged, reused as-is): `self._fire_on_resource_type_completed_for_link(...)`, `GraphLinkParameters(...)`, `AsyncParallelProcessor(...).process_rows_in_parallel(..., yield_context=True)`, `ResourceTypeStartedEvent`, `ResourceTypeCompletionEvent`, `GraphRetrievalStartedEvent`, `GraphRetrievalCompletedEvent` (all four dataclasses, all already imported at the top of `simulated_graph_processor_mixin.py`).
- Produces: `process_simulate_graph_async()`, `simulate_graph_async()`, and `simulate_graph_streaming_async()` all gain these keyword-only parameters, identical names/types/defaults across all three: `on_resource_type_completed: Callable[[ResourceTypeCompletionEvent], Awaitable[None]] | None = None`, `on_resource_type_started: Callable[[ResourceTypeStartedEvent], Awaitable[None]] | None = None`, `on_graph_retrieval_started: Callable[[GraphRetrievalStartedEvent], Awaitable[None]] | None = None`, `on_graph_retrieval_completed: Callable[[GraphRetrievalCompletedEvent], Awaitable[None]] | None = None`, `client_person_id: str = ""`, `connection_name: str = ""`, `continue_on_resource_type_error: bool = False`.

- [ ] **Step 1: Write the failing tests**

Create `helix_fhir_client_sdk/graph/test/test_simulate_graph_async_and_streaming_completion_hook.py`:

```python
from typing import Any

import pytest
from aioresponses import aioresponses

from helix_fhir_client_sdk.exceptions.fhir_sender_exception import FhirSenderException
from helix_fhir_client_sdk.graph.graph_retrieval_completed_event import (
    GraphRetrievalCompletedEvent,
)
from helix_fhir_client_sdk.graph.graph_retrieval_started_event import (
    GraphRetrievalStartedEvent,
)
from helix_fhir_client_sdk.graph.resource_type_completion_event import (
    ResourceTypeCompletionEvent,
)
from helix_fhir_client_sdk.graph.resource_type_started_event import (
    ResourceTypeStartedEvent,
)
from helix_fhir_client_sdk.graph.simulated_graph_processor_mixin import (
    SimulatedGraphProcessorMixin,
)
from helix_fhir_client_sdk.graph.test.test_simulate_graph_processor_mixin import (
    get_graph_processor,
)
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse

TWO_LINK_GRAPH: dict[str, Any] = {
    "id": "1",
    "name": "Test Graph",
    "resourceType": "GraphDefinition",
    "start": "Patient",
    "link": [
        {"target": [{"type": "AllergyIntolerance", "params": "patient={ref}"}]},
        {"target": [{"type": "CarePlan", "params": "patient={ref}"}]},
    ],
}

# No "link" key at all (GraphDefinition.from_dict defaults it to []) — used
# only by test_resource_type_completed_outcome_not_found_for_start_resource,
# where the parent bundle ends up holding one (bogus) OperationOutcome
# entry. TWO_LINK_GRAPH would make process_simulate_graph_async's existing,
# unmodified "if graph_definition.link and parent_bundle_entries:" line
# attempt to traverse links against that bogus entry — irrelevant to what
# that test is actually checking (start-resource outcome classification),
# so this fixture sidesteps it entirely.
START_ONLY_GRAPH: dict[str, Any] = {
    "id": "1",
    "name": "Test Graph - Start Only",
    "resourceType": "GraphDefinition",
    "start": "Patient",
}


def mock_two_link_graph_responses(m: aioresponses) -> None:
    m.get(
        "http://example.com/fhir/Patient/1",
        payload={"resourceType": "Patient", "id": "1"},
    )
    m.get(
        "http://example.com/fhir/AllergyIntolerance?patient=1",
        payload={"resourceType": "AllergyIntolerance", "id": "1"},
    )
    m.get(
        "http://example.com/fhir/CarePlan?patient=1",
        payload={"resourceType": "CarePlan", "id": "1"},
    )


async def call_graph_method(
    graph_processor: SimulatedGraphProcessorMixin,
    *,
    use_streaming: bool,
    **kwargs: Any,
) -> list[FhirGetResponse]:
    """Invokes whichever of the two public methods a parametrized test is
    exercising, and normalizes both call shapes (simulate_graph_async()
    awaits a single FhirGetResponse; simulate_graph_streaming_async() is an
    async generator) into a list, so the same assertions work for both."""
    if use_streaming:
        return [r async for r in graph_processor.simulate_graph_streaming_async(**kwargs)]
    return [await graph_processor.simulate_graph_async(**kwargs)]


USE_STREAMING_PARAMS = pytest.mark.parametrize(
    "use_streaming",
    [False, True],
    ids=["simulate_graph_async", "simulate_graph_streaming_async"],
)


@pytest.mark.asyncio
@USE_STREAMING_PARAMS
async def test_callbacks_default_to_none_is_noop(use_streaming: bool) -> None:
    # No callback passed — must behave exactly as before (regression guard
    # for the "zero behavior change for existing callers" constraint).
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    with aioresponses() as m:
        mock_two_link_graph_responses(m)

        responses = await call_graph_method(
            graph_processor,
            use_streaming=use_streaming,
            id_="1",
            graph_json=TWO_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
        )

    # Both methods accumulate the start resource + both links into one
    # merged FhirGetResponse — that shape is unchanged by this feature.
    assert len(responses) == 1
    assert responses[0].get_resource_count() == 3


@pytest.mark.asyncio
@USE_STREAMING_PARAMS
async def test_full_event_lifecycle_fires_in_order_at_concurrency_1(use_streaming: bool) -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    started_events: list[ResourceTypeStartedEvent] = []
    completed_events: list[ResourceTypeCompletionEvent] = []
    graph_started_events: list[GraphRetrievalStartedEvent] = []
    graph_completed_events: list[GraphRetrievalCompletedEvent] = []

    async def on_started(event: ResourceTypeStartedEvent) -> None:
        started_events.append(event)

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    async def on_graph_started(event: GraphRetrievalStartedEvent) -> None:
        graph_started_events.append(event)

    async def on_graph_completed(event: GraphRetrievalCompletedEvent) -> None:
        graph_completed_events.append(event)

    with aioresponses() as m:
        mock_two_link_graph_responses(m)

        responses = await call_graph_method(
            graph_processor,
            use_streaming=use_streaming,
            id_="1",
            graph_json=TWO_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
            on_resource_type_started=on_started,
            on_resource_type_completed=on_completed,
            on_graph_retrieval_started=on_graph_started,
            on_graph_retrieval_completed=on_graph_completed,
            client_person_id="client-1",
            connection_name="Aetna Sandbox",
        )

    assert len(responses) == 1
    assert responses[0].get_resource_count() == 3

    assert len(graph_started_events) == 1
    assert graph_started_events[0].start_resource_type == "Patient"
    assert graph_started_events[0].client_person_id == "client-1"
    assert graph_started_events[0].connection_name == "Aetna Sandbox"

    assert len(graph_completed_events) == 1
    assert sorted(graph_completed_events[0].resource_types) == sorted(["Patient", "AllergyIntolerance", "CarePlan"])
    assert graph_completed_events[0].total_resource_count == 3
    assert graph_completed_events[0].total_error_count == 0
    assert graph_completed_events[0].total_rejected_count == 0
    assert graph_completed_events[0].client_person_id == "client-1"
    assert graph_completed_events[0].connection_name == "Aetna Sandbox"

    # one started + one completed per resource type (start resource + 2 links)
    assert len(started_events) == 3
    assert len(completed_events) == 3
    assert started_events[0].resource_types == ["Patient"]
    assert started_events[0].link_index == -1
    assert completed_events[0].resource_types == ["Patient"]
    assert completed_events[0].outcome == "success"
    assert {t for e in completed_events[1:] for t in e.resource_types} == {"AllergyIntolerance", "CarePlan"}
    assert all(e.outcome == "success" for e in completed_events)

    # the (graph_depth, link_index) correlation key pairs each started event
    # with its own completed event, for the start resource and every link.
    for started_event, completed_event in zip(started_events, completed_events, strict=True):
        assert started_event.graph_depth == completed_event.graph_depth
        assert started_event.link_index == completed_event.link_index
    assert sorted(e.link_index for e in started_events[1:]) == [0, 1]


@pytest.mark.asyncio
@USE_STREAMING_PARAMS
async def test_resource_type_completed_fires_for_start_resource_with_genuinely_zero_results(
    use_streaming: bool,
) -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    completed_events: list[ResourceTypeCompletionEvent] = []

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    with aioresponses() as m:
        # An empty Bundle (zero entries) is a genuinely zero-result search
        # response — get_resource_count() == 0, so this hits the existing
        # early-return branch (unchanged by this feature).
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Bundle", "entry": []},
        )

        responses = await call_graph_method(
            graph_processor,
            use_streaming=use_streaming,
            id_="1",
            graph_json=TWO_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
            on_resource_type_completed=on_completed,
        )

    assert len(responses) == 1  # just the empty start-resource response
    assert responses[0].get_resource_count() == 0
    assert len(completed_events) == 1
    assert completed_events[0].resource_types == ["Patient"]
    assert completed_events[0].resource_count == 0
    assert completed_events[0].link_index == -1
    assert completed_events[0].outcome == "empty"


@pytest.mark.asyncio
@USE_STREAMING_PARAMS
async def test_resource_type_completed_outcome_not_found_for_start_resource(use_streaming: bool) -> None:
    # process_simulate_graph_async's own zero-vs-nonzero branching (unlike
    # _process_simulate_graph_by_resource_type_async's) is not changed by
    # this feature — get_resource_count() is 1 (not 0) for a
    # 404-with-OperationOutcome-body response, so this takes the "nonzero"
    # code path, not the early-return path. The reported outcome must still
    # be correctly classified as "not_found" regardless of which path ran —
    # that is what this test actually proves (see this plan's Global
    # Constraints and the design spec's Key Decision 4).
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    completed_events: list[ResourceTypeCompletionEvent] = []

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    with aioresponses() as m:
        m.get(
            "http://example.com/fhir/Patient/1",
            status=404,
            payload={"resourceType": "OperationOutcome"},
        )

        await call_graph_method(
            graph_processor,
            use_streaming=use_streaming,
            id_="1",
            graph_json=START_ONLY_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
            on_resource_type_completed=on_completed,
        )

    assert len(completed_events) == 1
    assert completed_events[0].resource_types == ["Patient"]
    assert completed_events[0].outcome == "not_found"


@pytest.mark.asyncio
@USE_STREAMING_PARAMS
async def test_graph_retrieval_completed_fires_exactly_once_on_start_resource_exception(
    use_streaming: bool,
) -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    graph_completed_events: list[GraphRetrievalCompletedEvent] = []

    async def on_graph_completed(event: GraphRetrievalCompletedEvent) -> None:
        graph_completed_events.append(event)

    with aioresponses() as m:
        m.get(
            "http://example.com/fhir/Patient/1",
            exception=RuntimeError("simulated network failure fetching start resource"),
        )

        with pytest.raises(FhirSenderException):
            await call_graph_method(
                graph_processor,
                use_streaming=use_streaming,
                id_="1",
                graph_json=TWO_LINK_GRAPH,
                contained=False,
                max_concurrent_tasks=1,
                on_graph_retrieval_completed=on_graph_completed,
            )

    assert len(graph_completed_events) == 1
    assert graph_completed_events[0].total_error_count == 1


@pytest.mark.asyncio
@USE_STREAMING_PARAMS
async def test_continue_on_resource_type_error_false_still_aborts(use_streaming: bool) -> None:
    # Default (False) must behave exactly as before this feature existed —
    # a link's fetch failure still aborts the whole traversal.
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

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
            await call_graph_method(
                graph_processor,
                use_streaming=use_streaming,
                id_="1",
                graph_json=TWO_LINK_GRAPH,
                contained=False,
                max_concurrent_tasks=1,
                continue_on_resource_type_error=False,
            )


@pytest.mark.asyncio
@USE_STREAMING_PARAMS
async def test_continue_on_resource_type_error_true_continues_past_link_failure(use_streaming: bool) -> None:
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

        responses = await call_graph_method(
            graph_processor,
            use_streaming=use_streaming,
            id_="1",
            graph_json=TWO_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
            continue_on_resource_type_error=True,
            on_resource_type_completed=on_completed,
            on_graph_retrieval_completed=on_graph_completed,
        )

    # Patient and CarePlan both made it into the merged response despite
    # AllergyIntolerance's fetch failing — the traversal did not abort.
    assert len(responses) == 1
    assert responses[0].get_resource_count() == 2

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
@USE_STREAMING_PARAMS
async def test_continue_on_resource_type_error_true_start_resource_still_fatal(use_streaming: bool) -> None:
    # The start resource's own fetch failure is always fatal, in every
    # mode — there are no links to traverse without it.
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    with aioresponses() as m:
        m.get(
            "http://example.com/fhir/Patient/1",
            exception=RuntimeError("simulated network failure fetching start resource"),
        )

        with pytest.raises(FhirSenderException):
            await call_graph_method(
                graph_processor,
                use_streaming=use_streaming,
                id_="1",
                graph_json=TWO_LINK_GRAPH,
                contained=False,
                max_concurrent_tasks=1,
                continue_on_resource_type_error=True,
            )


@pytest.mark.asyncio
@USE_STREAMING_PARAMS
async def test_full_event_lifecycle_stays_correct_at_concurrency_2(use_streaming: bool) -> None:
    # Regression guard for the AsyncParallelProcessor/CancelledError
    # concurrency-correctness fixes shipped with the original completion
    # hook feature (Task 10 there) — this call site is new, but the shared
    # machinery it wires into is not, so this proves the fix already covers
    # it too.
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=2)

    completed_events: list[ResourceTypeCompletionEvent] = []
    graph_completed_events: list[GraphRetrievalCompletedEvent] = []

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    async def on_graph_completed(event: GraphRetrievalCompletedEvent) -> None:
        graph_completed_events.append(event)

    with aioresponses() as m:
        mock_two_link_graph_responses(m)

        responses = await call_graph_method(
            graph_processor,
            use_streaming=use_streaming,
            id_="1",
            graph_json=TWO_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=2,
            on_resource_type_completed=on_completed,
            on_graph_retrieval_completed=on_graph_completed,
        )

    assert len(responses) == 1
    assert responses[0].get_resource_count() == 3

    non_start_events = [e for e in completed_events if e.resource_types != ["Patient"]]
    all_reported_types = [t for e in non_start_events for t in e.resource_types]
    assert sorted(all_reported_types) == sorted(["AllergyIntolerance", "CarePlan"])
    assert all(e.outcome == "success" for e in completed_events)

    assert len(graph_completed_events) == 1
    assert graph_completed_events[0].total_resource_count == 3
    assert graph_completed_events[0].total_error_count == 0


@pytest.mark.asyncio
@USE_STREAMING_PARAMS
async def test_resource_type_completed_outcome_scope_denied_for_link(use_streaming: bool) -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)
    graph_processor._auth_scopes = ["patient/Patient.read", "patient/CarePlan.read"]

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

        await call_graph_method(
            graph_processor,
            use_streaming=use_streaming,
            id_="1",
            graph_json=TWO_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
            on_resource_type_completed=on_completed,
            on_graph_retrieval_completed=on_graph_completed,
        )

    # AllergyIntolerance isn't in the granted scopes — its fetch never
    # happens at all, so it's reported as scope_denied, not empty.
    allergy_completed = [e for e in completed_events if e.resource_types == ["AllergyIntolerance"]]
    assert len(allergy_completed) == 1
    assert allergy_completed[0].outcome == "scope_denied"
    assert len(graph_completed_events) == 1
    assert graph_completed_events[0].total_rejected_count == 1
    assert graph_completed_events[0].total_error_count == 0


@pytest.mark.asyncio
@USE_STREAMING_PARAMS
async def test_resource_type_completed_outcome_error_for_non_404_http_status(use_streaming: bool) -> None:
    # Regression guard: this SDK's retry client returns (does not raise) for
    # HTTP 400/403 — only 5xx retries and then raises. A link whose fetch
    # came back 403 must be reported as outcome="error" with a synthesized
    # error_type, not fall through to "empty".
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
            status=403,
            payload={"resourceType": "OperationOutcome"},
        )
        m.get(
            "http://example.com/fhir/CarePlan?patient=1",
            payload={"resourceType": "CarePlan", "id": "1"},
        )

        await call_graph_method(
            graph_processor,
            use_streaming=use_streaming,
            id_="1",
            graph_json=TWO_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
            on_resource_type_completed=on_completed,
            on_graph_retrieval_completed=on_graph_completed,
        )

    allergy_completed = [e for e in completed_events if e.resource_types == ["AllergyIntolerance"]]
    assert len(allergy_completed) == 1
    assert allergy_completed[0].outcome == "error"
    assert allergy_completed[0].error_type == "HttpStatus403"
    assert allergy_completed[0].error_message == "Fetch failed with HTTP status 403"

    assert len(graph_completed_events) == 1
    assert graph_completed_events[0].total_error_count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest helix_fhir_client_sdk/graph/test/test_simulate_graph_async_and_streaming_completion_hook.py -v`
Expected: FAIL — `TypeError: SimulatedGraphProcessorMixin.simulate_graph_async() got an unexpected keyword argument 'on_resource_type_completed'` (and the same for `simulate_graph_streaming_async`).

- [ ] **Step 3: Add the new parameters to `process_simulate_graph_async()`'s signature**

In `helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py`, find:

```python
        compare_hash: bool = True,
        append_without_duplicate_removal: bool = False,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        Asynchronously simulate a FHIR $graph query with advanced processing capabilities.
```

Replace with:

```python
        compare_hash: bool = True,
        append_without_duplicate_removal: bool = False,
        on_resource_type_completed: (Callable[[ResourceTypeCompletionEvent], Awaitable[None]] | None) = None,
        on_resource_type_started: (Callable[[ResourceTypeStartedEvent], Awaitable[None]] | None) = None,
        on_graph_retrieval_started: (Callable[[GraphRetrievalStartedEvent], Awaitable[None]] | None) = None,
        on_graph_retrieval_completed: (Callable[[GraphRetrievalCompletedEvent], Awaitable[None]] | None) = None,
        client_person_id: str = "",
        connection_name: str = "",
        continue_on_resource_type_error: bool = False,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        Asynchronously simulate a FHIR $graph query with advanced processing capabilities.
```

(`Callable`, `Awaitable`, and all four event dataclasses are already imported at the top of this file — no new imports needed.)

- [ ] **Step 4: Document the new parameters in `process_simulate_graph_async()`'s docstring**

Find:

```python
            compare_hash: Flag to compare resource hashes for changes

        Yields:
            FhirGetResponse objects representing retrieved resources
        """
```

Replace with:

```python
            compare_hash: Flag to compare resource hashes for changes
            on_resource_type_completed: Optional async callback invoked once the start
                resource has been retrieved, and again each time one graph link's
                resources have been fully retrieved — independent of when/whether that
                data is actually yielded to this generator's own caller, since this method
                always accumulates every link's resources and yields once (see
                on_graph_retrieval_completed below). Fires with a
                ResourceTypeCompletionEvent. Defaults to None (no-op, zero behavior change).
            on_resource_type_started: Optional async callback invoked once per graph link
                (or the start resource) right before that link's resources begin
                retrieving. Fires with a ResourceTypeStartedEvent. Defaults to None (no-op,
                zero behavior change).
            on_graph_retrieval_started: Optional async callback invoked exactly once,
                before the start resource is fetched. Fires with a
                GraphRetrievalStartedEvent. Defaults to None (no-op, zero behavior change).
            on_graph_retrieval_completed: Optional async callback invoked exactly once,
                after the traversal finishes (including the zero-results early return),
                and also when an exception propagates from inside the traversal or the
                caller stops consuming this generator early via an explicit
                break/aclose(). Fires with a GraphRetrievalCompletedEvent. Defaults to
                None (no-op, zero behavior change).
            client_person_id: Optional caller-supplied, opaque identifier for the person
                this call belongs to. Not interpreted by this SDK — echoed back on every
                fired event so a callback shared across multiple concurrent calls can tell
                them apart. Defaults to "".
            connection_name: Optional caller-supplied, opaque display name for the
                connection this call belongs to. Not interpreted by this SDK — echoed back
                on every fired event for the same reason as client_person_id. Defaults to
                "".
            continue_on_resource_type_error: Optional flag (default False, preserving
                today's exact behavior). When True, a link's own fetch failure fires
                on_resource_type_completed with outcome="error" and the traversal
                continues to the next link instead of re-raising. The start resource's own
                fetch failure is always fatal, regardless of this flag.

        Yields:
            FhirGetResponse objects representing retrieved resources
        """
```

- [ ] **Step 5: Run mypy to confirm the signature/docstring change alone is still clean**

Run: `uv run mypy helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py`
Expected: no new errors (the new parameters are unused so far — that's expected and harmless at this point).

- [ ] **Step 6: Rewrite `process_simulate_graph_async()`'s body to wire in the start-resource lifecycle, per-link lifecycle, and bookend events**

Find this entire block (from just after the docstring's closing `"""` through the end of the method body):

```python
        id_search_unsupported_resources: list[str] = []
        cache: RequestCache = input_cache if input_cache is not None else RequestCache()
        async with cache:
            # Retrieve start resources based on graph definition
            start: str = graph_definition.start
            parent_response: FhirGetResponse
            cache_hits: int
            parent_response, cache_hits = await self._get_resources_by_parameters_async(
                resource_type=start,
                id_=id_,
                cache=cache,
                scope_parser=scope_parser,
                logger=logger,
                id_search_unsupported_resources=id_search_unsupported_resources,
                add_cached_bundles_to_result=add_cached_bundles_to_result,
                compare_hash=compare_hash,
            )

            # If no parent resources found, yield empty response and exit
            parent_response_resource_count = parent_response.get_resource_count()
            if parent_response_resource_count == 0:
                yield parent_response
                return  # no resources to process

            # Log parent resource retrieval details
            if logger:
                logger.info(
                    f"FhirClient.simulate_graph_async() "
                    f"got parent resources: {parent_response_resource_count} "
                    f"cached:{cache_hits}"
                )

            # Prepare parent bundle entries for further processing
            parent_bundle_entries: FhirBundleEntryList = parent_response.get_bundle_entries()
            if logger:
                logger.info(
                    f"FhirClient.simulate_graph_async() got parent resources: {parent_response_resource_count} "
                    + f"cached:{cache_hits}"
                )

            # now process the graph links
            child_responses: list[FhirGetResponse] = []
            parent_link_map: list[tuple[list[GraphDefinitionLink], FhirBundleEntryList]] = []

            # Add initial graph links if defined
            if graph_definition.link and parent_bundle_entries:
                parent_link_map.append((graph_definition.link, parent_bundle_entries))

            # Process graph links in parallel
            while len(parent_link_map):
                new_parent_link_map: list[tuple[list[GraphDefinitionLink], FhirBundleEntryList]] = []

                # Parallel processing of links for each parent bundle
                for link, parent_bundle_entries in parent_link_map:
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

                # Update parent link map for next iteration
                parent_link_map = new_parent_link_map

            start_time = time.time()
            # Combine and process responses
            if not append_without_duplicate_removal:
                parent_response = cast(FhirGetBundleResponse, parent_response.extend(child_responses))
            else:
                parent_response = cast(
                    FhirGetBundleResponse,
                    parent_response._append_without_duplicate_removal(child_responses),
                )
            if logger:
                logger.info(f"Parent_response.extend time: {time.time() - start_time}")

            # Optional resource sorting
            if sort_resources:
                parent_response = parent_response.sort_resources()

            # Prepare final response based on bundling preferences
            full_response: FhirGetResponse
            if separate_bundle_resources:
                full_response = FhirGetListByResourceTypeResponse.from_response(other_response=parent_response)
            elif expand_fhir_bundle:
                full_response = FhirGetListResponse.from_response(other_response=parent_response)
            else:
                full_response = parent_response

            # Set response URL
            full_response.url = url or parent_response.url

            # Log cache performance
            if logger:
                logger.info(
                    f"Request Cache for: id_={id_}, "
                    f"start={graph_definition.start}, "
                    f"hits: {cache.cache_hits}, "
                    f"misses: {cache.cache_misses}"
                )

            # Yield the final response
            yield full_response
```

Replace with:

```python
        id_search_unsupported_resources: list[str] = []
        cache: RequestCache = input_cache if input_cache is not None else RequestCache()

        # Aggregation state for the graph-level completion event. Initialized
        # here — before anything below that can raise — so the `finally`
        # block guarding on_graph_retrieval_completed can always build a
        # GraphRetrievalCompletedEvent from *some* valid state, even if an
        # exception propagates partway through the traversal or the caller
        # closes/abandons the generator early.
        all_resource_types: set[str] = set()
        total_resource_count: int = 0
        max_graph_depth: int = 0
        all_urls: set[str] = set()
        total_error_count: int = 0
        total_rejected_count: int = 0

        async with cache:
            start: str = graph_definition.start
            try:
                if on_graph_retrieval_started:
                    await on_graph_retrieval_started(
                        GraphRetrievalStartedEvent(
                            start_resource_type=start,
                            url=url or "",
                            client_person_id=client_person_id,
                            connection_name=connection_name,
                        )
                    )

                if on_resource_type_started:
                    await on_resource_type_started(
                        ResourceTypeStartedEvent(
                            resource_types=[start],
                            graph_depth=0,
                            url=url or "",
                            link_index=-1,
                            client_person_id=client_person_id,
                            connection_name=connection_name,
                        )
                    )

                # Retrieve start resources based on graph definition
                parent_response: FhirGetResponse
                cache_hits: int
                try:
                    parent_response, cache_hits = await self._get_resources_by_parameters_async(
                        resource_type=start,
                        id_=id_,
                        cache=cache,
                        scope_parser=scope_parser,
                        logger=logger,
                        id_search_unsupported_resources=id_search_unsupported_resources,
                        add_cached_bundles_to_result=add_cached_bundles_to_result,
                        compare_hash=compare_hash,
                    )
                except (Exception, asyncio.CancelledError, GeneratorExit) as exc:
                    # See the identical except-clause in
                    # _process_simulate_graph_by_resource_type_async for why
                    # asyncio.CancelledError/GeneratorExit are caught
                    # explicitly here alongside Exception (both are
                    # BaseException, not Exception), and why this never
                    # suppresses the exception — it always re-raises.
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

                # The reported outcome is computed from the response's
                # actual status/content, independent of the branching
                # decision below — that branching stays exactly as it was
                # before this feature (raw get_resource_count(), not the
                # OperationOutcome-excluding content check
                # _process_simulate_graph_by_resource_type_async uses), per
                # this plan's Global Constraints. This must still be
                # computed before the branch so a 404-with-body response
                # (get_resource_count() == 1, not 0 — the OperationOutcome
                # itself counts) reports outcome="not_found" correctly even
                # though it takes the "nonzero" branch below, not the
                # early-return one.
                parent_response_resource_count = parent_response.get_resource_count()
                start_resource_outcome: Literal["success", "empty", "not_found", "scope_denied", "error"] = (
                    "not_found"
                    if parent_response.status == 404
                    else "error"
                    if not parent_response.successful
                    else "success"
                    if parent_response_resource_count > 0
                    else "empty"
                )
                start_resource_error_type = (
                    f"HttpStatus{parent_response.status}"
                    if not parent_response.successful and parent_response.status != 404
                    else None
                )
                start_resource_error_message = (
                    f"Fetch failed with HTTP status {parent_response.status}"
                    if not parent_response.successful and parent_response.status != 404
                    else None
                )

                # If no parent resources found, yield empty response and exit
                if parent_response_resource_count == 0:
                    yield parent_response
                    if on_resource_type_completed:
                        await on_resource_type_completed(
                            ResourceTypeCompletionEvent(
                                resource_types=[start],
                                resource_count=parent_response_resource_count,
                                graph_depth=0,
                                urls=[parent_response.url] if parent_response.url else [],
                                link_index=-1,
                                client_person_id=client_person_id,
                                connection_name=connection_name,
                                outcome=start_resource_outcome,
                                error_type=start_resource_error_type,
                                error_message=start_resource_error_message,
                            )
                        )
                    if start_resource_outcome == "error":
                        total_error_count += 1
                    return  # no resources to process

                # Log parent resource retrieval details
                if logger:
                    logger.info(
                        f"FhirClient.simulate_graph_async() "
                        f"got parent resources: {parent_response_resource_count} "
                        f"cached:{cache_hits}"
                    )

                all_resource_types.add(start)
                total_resource_count += parent_response_resource_count
                if parent_response.url:
                    all_urls.add(parent_response.url)

                if on_resource_type_completed:
                    await on_resource_type_completed(
                        ResourceTypeCompletionEvent(
                            resource_types=[start],
                            resource_count=parent_response_resource_count,
                            graph_depth=0,
                            urls=[parent_response.url] if parent_response.url else [],
                            link_index=-1,
                            client_person_id=client_person_id,
                            connection_name=connection_name,
                            outcome=start_resource_outcome,
                            error_type=start_resource_error_type,
                            error_message=start_resource_error_message,
                        )
                    )
                if start_resource_outcome == "error":
                    total_error_count += 1

                # Prepare parent bundle entries for further processing
                parent_bundle_entries: FhirBundleEntryList = parent_response.get_bundle_entries()
                if logger:
                    logger.info(
                        f"FhirClient.simulate_graph_async() got parent resources: {parent_response_resource_count} "
                        + f"cached:{cache_hits}"
                    )

                # now process the graph links
                child_responses: list[FhirGetResponse] = []
                parent_link_map: list[tuple[list[GraphDefinitionLink], FhirBundleEntryList]] = []

                # Add initial graph links if defined
                if graph_definition.link and parent_bundle_entries:
                    parent_link_map.append((graph_definition.link, parent_bundle_entries))

                def _record_link_fetch_error() -> None:
                    """Counts one genuine link fetch failure. See the
                    identical helper in
                    _process_simulate_graph_by_resource_type_async for why
                    this must be a dedicated callback rather than a
                    try/except around the consumer loop below."""
                    nonlocal total_error_count
                    total_error_count += 1

                async def _record_link_batch_outcome(
                    *,
                    link_responses: list[FhirGetResponse],
                    link_queried_urls: list[str],
                    links: list[GraphDefinitionLink],
                    context: ParallelFunctionContext,
                    error: Exception | None,
                ) -> Literal["success", "empty", "not_found", "scope_denied", "error"]:
                    """Aggregates one link batch's results into the
                    whole-graph rollups and fires its completion event.
                    Behaviorally identical to
                    _process_simulate_graph_by_resource_type_async's own
                    nested closure of the same name — duplicated rather than
                    shared because each closes over its own method's local
                    aggregation variables via `nonlocal`."""
                    nonlocal all_resource_types, total_resource_count, max_graph_depth, all_urls
                    resource_types = sorted({r.resource_type for r in link_responses if r.resource_type})
                    resource_count_for_link = sum(r.get_resource_count() for r in link_responses)

                    if resource_types:
                        all_resource_types.update(resource_types)
                        total_resource_count += resource_count_for_link
                        max_graph_depth = graph_depth
                    all_urls.update(link_queried_urls)

                    return await self._fire_on_resource_type_completed_for_link(
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
                        error=error,
                    )

                # Process graph links in parallel
                graph_depth = 0
                while len(parent_link_map):
                    new_parent_link_map: list[tuple[list[GraphDefinitionLink], FhirBundleEntryList]] = []

                    # Parallel processing of links for each parent bundle
                    for link, parent_bundle_entries in parent_link_map:
                        context: ParallelFunctionContext
                        link_fetch_result: _LinkFetchResult
                        async for context, link_fetch_result in AsyncParallelProcessor(  # type: ignore[misc]
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
                                on_resource_type_started=on_resource_type_started,
                                on_resource_type_completed=on_resource_type_completed,
                                graph_depth=graph_depth,
                                url=url or "",
                                client_person_id=client_person_id,
                                connection_name=connection_name,
                                continue_on_resource_type_error=continue_on_resource_type_error,
                                on_link_fetch_error=_record_link_fetch_error,
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
                            link_queried_urls = [r.url for r in link_responses if r.url]
                            child_responses.extend(link_responses)

                            outcome = await _record_link_batch_outcome(
                                link_responses=link_responses,
                                link_queried_urls=link_queried_urls,
                                links=link,
                                context=context,
                                error=link_fetch_result.error,
                            )
                            if outcome == "error":
                                total_error_count += 1
                            elif outcome == "scope_denied":
                                total_rejected_count += 1

                    # Update parent link map for next iteration
                    parent_link_map = new_parent_link_map
                    graph_depth += 1

                start_time = time.time()
                # Combine and process responses
                if not append_without_duplicate_removal:
                    parent_response = cast(FhirGetBundleResponse, parent_response.extend(child_responses))
                else:
                    parent_response = cast(
                        FhirGetBundleResponse,
                        parent_response._append_without_duplicate_removal(child_responses),
                    )
                if logger:
                    logger.info(f"Parent_response.extend time: {time.time() - start_time}")

                # Optional resource sorting
                if sort_resources:
                    parent_response = parent_response.sort_resources()

                # Prepare final response based on bundling preferences
                full_response: FhirGetResponse
                if separate_bundle_resources:
                    full_response = FhirGetListByResourceTypeResponse.from_response(other_response=parent_response)
                elif expand_fhir_bundle:
                    full_response = FhirGetListResponse.from_response(other_response=parent_response)
                else:
                    full_response = parent_response

                # Set response URL
                full_response.url = url or parent_response.url

                # Log cache performance
                if logger:
                    logger.info(
                        f"Request Cache for: id_={id_}, "
                        f"start={graph_definition.start}, "
                        f"hits: {cache.cache_hits}, "
                        f"misses: {cache.cache_misses}"
                    )

                # Yield the final response
                yield full_response
            finally:
                # Fires exactly once per call — see the identical `finally`
                # block in _process_simulate_graph_by_resource_type_async for
                # the full reasoning (normal completion, exception, or the
                # caller closing/abandoning this generator early).
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
                    )
```

- [ ] **Step 7: Add the new parameters to `simulate_graph_async()`'s signature, docstring, and forwarded call**

Find:

```python
        compare_hash: bool = True,
        append_without_duplicate_removal: bool = False,
    ) -> FhirGetResponse:
```

Replace with:

```python
        compare_hash: bool = True,
        append_without_duplicate_removal: bool = False,
        on_resource_type_completed: (Callable[[ResourceTypeCompletionEvent], Awaitable[None]] | None) = None,
        on_resource_type_started: (Callable[[ResourceTypeStartedEvent], Awaitable[None]] | None) = None,
        on_graph_retrieval_started: (Callable[[GraphRetrievalStartedEvent], Awaitable[None]] | None) = None,
        on_graph_retrieval_completed: (Callable[[GraphRetrievalCompletedEvent], Awaitable[None]] | None) = None,
        client_person_id: str = "",
        connection_name: str = "",
        continue_on_resource_type_error: bool = False,
    ) -> FhirGetResponse:
```

Find (inside `simulate_graph_async()`'s docstring):

```python
        :param compare_hash: Optional flag to compare hash of the resources
        :return: FhirGetResponse
        """
        if contained:
```

Replace with:

```python
        :param compare_hash: Optional flag to compare hash of the resources
        :param on_resource_type_completed: Optional async callback invoked once the start
                                             resource has been retrieved, and again each
                                             time one graph link's resources have been
                                             fully retrieved. Fires with a
                                             ResourceTypeCompletionEvent. Defaults to None
                                             (no-op, zero behavior change).
        :param on_resource_type_started: Optional async callback invoked once per graph
                                           link (or the start resource) right before that
                                           link's resources begin retrieving. Fires with a
                                           ResourceTypeStartedEvent. Defaults to None (no-op,
                                           zero behavior change).
        :param on_graph_retrieval_started: Optional async callback invoked exactly once,
                                             before the start resource is fetched. Fires with
                                             a GraphRetrievalStartedEvent. Defaults to None
                                             (no-op, zero behavior change).
        :param on_graph_retrieval_completed: Optional async callback invoked exactly once,
                                               after the traversal finishes retrieving every
                                               resource (including the zero-results early
                                               return), and also on an exception. Fires with
                                               a GraphRetrievalCompletedEvent. Defaults to
                                               None (no-op, zero behavior change).
        :param client_person_id: Optional caller-supplied, opaque identifier for the
                                    person this call belongs to. Not interpreted by this
                                    SDK — echoed back on every fired event. Defaults to "".
        :param connection_name: Optional caller-supplied, opaque display name for the
                                   connection this call belongs to. Not interpreted by
                                   this SDK — echoed back on every fired event. Defaults
                                   to "".
        :param continue_on_resource_type_error: Optional flag (default False, preserving
                                                   today's exact behavior). When True, a
                                                   link's own fetch failure fires
                                                   on_resource_type_completed with
                                                   outcome="error" and the traversal
                                                   continues to the next link instead of
                                                   re-raising. The start resource's own
                                                   fetch failure is always fatal,
                                                   regardless of this flag.
        :return: FhirGetResponse
        """
        if contained:
```

Find:

```python
                compare_hash=compare_hash,
                append_without_duplicate_removal=append_without_duplicate_removal,
            )
        )
        assert result, "No result returned from simulate_graph_async"
        return result
```

Replace with:

```python
                compare_hash=compare_hash,
                append_without_duplicate_removal=append_without_duplicate_removal,
                on_resource_type_completed=on_resource_type_completed,
                on_resource_type_started=on_resource_type_started,
                on_graph_retrieval_started=on_graph_retrieval_started,
                on_graph_retrieval_completed=on_graph_retrieval_completed,
                client_person_id=client_person_id,
                connection_name=connection_name,
                continue_on_resource_type_error=continue_on_resource_type_error,
            )
        )
        assert result, "No result returned from simulate_graph_async"
        return result
```

- [ ] **Step 8: Add the new parameters to `simulate_graph_streaming_async()`'s signature, docstring, and forwarded call (with explicit `aclose()`)**

Find:

```python
        sort_resources: bool | None = False,
        input_cache: RequestCache | None = None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
```

Replace with:

```python
        sort_resources: bool | None = False,
        input_cache: RequestCache | None = None,
        on_resource_type_completed: (Callable[[ResourceTypeCompletionEvent], Awaitable[None]] | None) = None,
        on_resource_type_started: (Callable[[ResourceTypeStartedEvent], Awaitable[None]] | None) = None,
        on_graph_retrieval_started: (Callable[[GraphRetrievalStartedEvent], Awaitable[None]] | None) = None,
        on_graph_retrieval_completed: (Callable[[GraphRetrievalCompletedEvent], Awaitable[None]] | None) = None,
        client_person_id: str = "",
        connection_name: str = "",
        continue_on_resource_type_error: bool = False,
    ) -> AsyncGenerator[FhirGetResponse, None]:
```

Find (inside `simulate_graph_streaming_async()`'s docstring):

```python
        :param input_cache: Optional cache to use for input
        :return: FhirGetResponse
        """
        if contained:
```

Replace with:

```python
        :param input_cache: Optional cache to use for input
        :param on_resource_type_completed: Optional async callback invoked once the start
                                             resource has been retrieved, and again each
                                             time one graph link's resources have been
                                             fully retrieved. Fires with a
                                             ResourceTypeCompletionEvent. Defaults to None
                                             (no-op, zero behavior change).
        :param on_resource_type_started: Optional async callback invoked once per graph
                                           link (or the start resource) right before that
                                           link's resources begin retrieving. Fires with a
                                           ResourceTypeStartedEvent. Defaults to None (no-op,
                                           zero behavior change).
        :param on_graph_retrieval_started: Optional async callback invoked exactly once,
                                             before the start resource is fetched. Fires with
                                             a GraphRetrievalStartedEvent. Defaults to None
                                             (no-op, zero behavior change).
        :param on_graph_retrieval_completed: Optional async callback invoked exactly once,
                                               after the traversal finishes retrieving every
                                               resource (including the zero-results early
                                               return), and also when an exception
                                               propagates or the caller stops consuming this
                                               generator early via an explicit
                                               break/aclose(). Fires with a
                                               GraphRetrievalCompletedEvent. Defaults to
                                               None (no-op, zero behavior change).
        :param client_person_id: Optional caller-supplied, opaque identifier for the
                                    person this call belongs to. Not interpreted by this
                                    SDK — echoed back on every fired event. Defaults to "".
        :param connection_name: Optional caller-supplied, opaque display name for the
                                   connection this call belongs to. Not interpreted by
                                   this SDK — echoed back on every fired event. Defaults
                                   to "".
        :param continue_on_resource_type_error: Optional flag (default False, preserving
                                                   today's exact behavior). When True, a
                                                   link's own fetch failure fires
                                                   on_resource_type_completed with
                                                   outcome="error" and the traversal
                                                   continues to the next link instead of
                                                   re-raising. The start resource's own
                                                   fetch failure is always fatal,
                                                   regardless of this flag.
        :return: FhirGetResponse
        """
        if contained:
```

Find:

```python
        async for r in self.process_simulate_graph_async(
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
            input_cache=input_cache,
        ):
            yield r
```

Replace with:

```python
        inner_generator = self.process_simulate_graph_async(
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
            input_cache=input_cache,
            on_resource_type_completed=on_resource_type_completed,
            on_resource_type_started=on_resource_type_started,
            on_graph_retrieval_started=on_graph_retrieval_started,
            on_graph_retrieval_completed=on_graph_retrieval_completed,
            client_person_id=client_person_id,
            connection_name=connection_name,
            continue_on_resource_type_error=continue_on_resource_type_error,
        )
        try:
            async for r in inner_generator:
                yield r
        finally:
            # See the identical wrapping in simulate_graph_by_resource_type_async
            # for why this explicit aclose() is needed: it makes the inner
            # generator's own try/finally (where on_graph_retrieval_completed
            # fires) run synchronously as part of closing this wrapper
            # generator, rather than deferred to asyncio's asyncgen finalizer.
            await inner_generator.aclose()
```

- [ ] **Step 9: Run the new tests to verify they pass**

Run: `uv run pytest helix_fhir_client_sdk/graph/test/test_simulate_graph_async_and_streaming_completion_hook.py -v`
Expected: all tests PASS (24 test cases: 12 test functions × 2 `use_streaming` parameterizations).

- [ ] **Step 10: Run the existing graph test suite to confirm no regressions**

Run: `uv run pytest helix_fhir_client_sdk/graph/test/ -v`
Expected: all tests PASS, including every existing `simulate_graph_by_resource_type_async()`, `simulate_graph_async()`, and `simulate_graph_streaming_async()` test that predates this change.

- [ ] **Step 11: Run mypy --strict on the modified file**

Run: `uv run mypy helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py`
Expected: no errors. If mypy complains about the `# type: ignore[misc]` comment being unused or about the `context`/`link_fetch_result` tuple-unpacking, compare against the identical pattern already in `_process_simulate_graph_by_resource_type_async` (same file) — that method already exercises the same `process_rows_in_parallel(..., yield_context=True)` call shape successfully under `mypy --strict`.

- [ ] **Step 12: Commit**

```bash
git add helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py \
        helix_fhir_client_sdk/graph/test/test_simulate_graph_async_and_streaming_completion_hook.py
git commit -m "TICKET-TBD extend completion-hook event lifecycle to simulate_graph_async() and simulate_graph_streaming_async()"
```

---

## Task 2: Fix stale docstrings on the event dataclasses and `GraphLinkParameters`

**Files:**
- Modify: `helix_fhir_client_sdk/graph/resource_type_started_event.py`
- Modify: `helix_fhir_client_sdk/graph/resource_type_completion_event.py`
- Modify: `helix_fhir_client_sdk/graph/graph_retrieval_started_event.py`
- Modify: `helix_fhir_client_sdk/graph/graph_retrieval_completed_event.py`
- Modify: `helix_fhir_client_sdk/graph/graph_link_parameters.py`

**Interfaces:** None — this task changes only docstrings/comments, no code, no new fields, no signature changes.

Every one of these five files currently describes the event lifecycle as exclusive to `simulate_graph_by_resource_type_async()` (e.g. "Emitted by simulate_graph_by_resource_type_async()...") or names `simulate_graph_async()` as an example of a caller that leaves a field at its default (e.g. "None for callers that don't use simulate_graph_by_resource_type_async's per-resource-type hooks (e.g. simulate_graph_async)"). After Task 1, both of those statements are now inaccurate — comment accuracy matters, so this task corrects them. There is no new behavior here, so there are no new tests; the existing full test suite (run in Step 2 below) is the verification.

- [ ] **Step 1: Update the docstrings**

In `helix_fhir_client_sdk/graph/resource_type_started_event.py`, find:

```python
    """
    Emitted by simulate_graph_by_resource_type_async() right before it begins
    retrieving one GraphDefinition link's resource type(s), or the start
    resource itself. Fires once per link (mirroring
    ResourceTypeCompletionEvent), before any HTTP request for that link has
    completed.
    """
```

Replace with:

```python
    """
    Emitted by simulate_graph_by_resource_type_async(), simulate_graph_async(),
    and simulate_graph_streaming_async() right before retrieval begins for one
    GraphDefinition link's resource type(s), or the start resource itself.
    Fires once per link (mirroring ResourceTypeCompletionEvent), before any
    HTTP request for that link has completed.
    """
```

In `helix_fhir_client_sdk/graph/resource_type_completion_event.py`, find:

```python
    """
    Emitted by simulate_graph_by_resource_type_async() after every resource that
    belongs to one GraphDefinition link (usually one resource type, occasionally
    more than one if the link's `target` array names several types) has been
    yielded to the caller. There is nothing left to wait for regarding these
    resource type(s) at this graph depth once this event fires.
    """
```

Replace with:

```python
    """
    Emitted by simulate_graph_by_resource_type_async(), simulate_graph_async(),
    and simulate_graph_streaming_async() after every resource that belongs to
    one GraphDefinition link (usually one resource type, occasionally more
    than one if the link's `target` array names several types) has been
    fully retrieved (usually — but not always, see simulate_graph_async()'s
    and simulate_graph_streaming_async()'s own docstrings — also yielded to
    the caller at that point). There is nothing left to wait for regarding
    these resource type(s) at this graph depth once this event fires.
    """
```

In `helix_fhir_client_sdk/graph/graph_retrieval_started_event.py`, find:

```python
    """
    Emitted exactly once by simulate_graph_by_resource_type_async(), before
    the start resource is fetched — the first thing the method does. Useful
    for "connecting..." progress UI.
    """
```

Replace with:

```python
    """
    Emitted exactly once by simulate_graph_by_resource_type_async(),
    simulate_graph_async(), and simulate_graph_streaming_async(), before the
    start resource is fetched — the first thing each of those methods does.
    Useful for "connecting..." progress UI.
    """
```

In `helix_fhir_client_sdk/graph/graph_retrieval_completed_event.py`, find:

```python
    """
    Emitted exactly once by simulate_graph_by_resource_type_async(), after
    every resource in the graph has been yielded — the last thing the method
    does before returning (including the early-return path where the start
    resource itself returned zero results). Useful for "done" progress UI.
    """
```

Replace with:

```python
    """
    Emitted exactly once by simulate_graph_by_resource_type_async(),
    simulate_graph_async(), and simulate_graph_streaming_async(), after the
    traversal finishes retrieving every resource in the graph — the last
    thing each of those methods does before returning (including the
    early-return path where the start resource itself returned zero
    results). Useful for "done" progress UI.
    """
```

In `helix_fhir_client_sdk/graph/graph_link_parameters.py`, find each of the five occurrences of the phrase `(e.g. simulate_graph_async)` (in the docstrings of `on_resource_type_started`, `on_resource_type_completed`, `client_person_id`, `connection_name`, and `on_link_fetch_error`) and the one occurrence of `Not consulted by simulate_graph_async() (the non-streaming sibling method), which never sets it and so always gets the default False.` (in `continue_on_resource_type_error`'s docstring). Remove all six — `simulate_graph_async()` now sets every one of these fields when its own caller passes the corresponding parameter, so it's no longer an accurate example of a caller that doesn't. For example, find:

```python
    on_resource_type_started: Callable[[ResourceTypeStartedEvent], Awaitable[None]] | None = None
    """Optional callback fired once per row (GraphDefinitionLink) right
    before that link's resources begin retrieving. None for callers that
    don't use simulate_graph_by_resource_type_async's per-resource-type
    hooks (e.g. simulate_graph_async)."""
```

Replace with:

```python
    on_resource_type_started: Callable[[ResourceTypeStartedEvent], Awaitable[None]] | None = None
    """Optional callback fired once per row (GraphDefinitionLink) right
    before that link's resources begin retrieving. None for a caller of
    simulate_graph_by_resource_type_async(), simulate_graph_async(), or
    simulate_graph_streaming_async() that doesn't use that method's
    per-resource-type hooks."""
```

Apply the same substitution pattern (removing the "(e.g. simulate_graph_async)" / "which never sets it..." phrasing and replacing it with the more general "a caller ... that doesn't use that method's per-resource-type hooks" phrasing) to the remaining four field docstrings in that file (`on_resource_type_completed`, `client_person_id`, `connection_name`, `on_link_fetch_error`) and to `continue_on_resource_type_error`'s docstring (drop its final sentence entirely, since it's no longer true).

- [ ] **Step 2: Run the full test suite to confirm no regressions**

Run: `uv run pytest helix_fhir_client_sdk/graph/test/ -v`
Expected: all tests PASS (docstring-only change; no test assertions reference docstring text).

- [ ] **Step 3: Run mypy**

Run: `uv run mypy helix_fhir_client_sdk/graph/`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add helix_fhir_client_sdk/graph/resource_type_started_event.py \
        helix_fhir_client_sdk/graph/resource_type_completion_event.py \
        helix_fhir_client_sdk/graph/graph_retrieval_started_event.py \
        helix_fhir_client_sdk/graph/graph_retrieval_completed_event.py \
        helix_fhir_client_sdk/graph/graph_link_parameters.py
git commit -m "TICKET-TBD fix event/GraphLinkParameters docstrings now that simulate_graph_async() and simulate_graph_streaming_async() also emit these events"
```

---

## Task 3: Full-suite verification and final commit

**Files:** None modified — this task only runs verification commands.

**Interfaces:** None.

- [ ] **Step 1: Run the full repository test suite**

Run: `uv run pytest helix_fhir_client_sdk/ -v`
Expected: all tests PASS (this repo's `README`/CI convention — confirm via `Makefile`/`pyproject.toml` if a different invocation is canonical; do not invent a different command).

- [ ] **Step 2: Run mypy --strict across the whole package**

Run: `uv run mypy helix_fhir_client_sdk/`
Expected: no errors.

- [ ] **Step 3: Run ruff**

Run: `uv run ruff check helix_fhir_client_sdk/` and `uv run ruff format --check helix_fhir_client_sdk/`
Expected: no errors/no reformatting needed. If `ruff format --check` reports a diff, run `uv run ruff format helix_fhir_client_sdk/` and re-review the diff before amending Task 1/2's commits.

- [ ] **Step 4: Replace the `TICKET-TBD` placeholder**

Once a real JIRA ticket key exists for this work, rewrite every commit message from this plan (`git rebase -i` against the branch point, or `git commit --amend` if there's only one commit left to fix) to use it instead of `TICKET-TBD`, per this org's commit-message convention.

- [ ] **Step 5: Final commit / summary**

If Step 4 produced new commits (via amend/rebase), no further commit is needed here. Otherwise, this task requires no commit of its own — it's verification-only.
