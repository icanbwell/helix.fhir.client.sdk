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

# A path-based link whose target never matches anything on the returned
# Patient resource (no "generalPractitioner" property in the mocked payload
# below), so process_link_async_parallel_function returns an empty list for
# this link — exercising the "link returns zero resources" fallback path for
# on_resource_type_completed (Design Decision 3).
PATH_LINK_GRAPH: dict[str, Any] = {
    "id": "1",
    "name": "Test Graph - Path Link",
    "resourceType": "GraphDefinition",
    "start": "Patient",
    "link": [
        {"path": "generalPractitioner", "target": [{"type": "Practitioner"}]},
    ],
}

# NESTED_GRAPH: Patient -> Encounter (depth 0) -> Practitioner (depth 1),
# matching the target.link nesting shape from
# test_graph_definition_with_nested_links in test_simulate_graph_processor_mixin.py.
NESTED_GRAPH: dict[str, Any] = {
    "id": "1",
    "name": "Test Graph - Nested",
    "resourceType": "GraphDefinition",
    "start": "Patient",
    "link": [
        {
            "target": [
                {
                    "type": "Encounter",
                    "params": "patient={ref}",
                    "link": [
                        {
                            "target": [
                                {
                                    "type": "Practitioner",
                                    "params": "encounter={ref}",
                                }
                            ]
                        }
                    ],
                }
            ]
        }
    ],
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


@pytest.mark.asyncio
async def test_on_resource_type_completed_fires_once_per_link() -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    events: list[ResourceTypeCompletionEvent] = []

    async def capture(event: ResourceTypeCompletionEvent) -> None:
        events.append(event)

    with aioresponses() as m:
        mock_two_link_graph_responses(m)

        responses = [
            r
            async for r in graph_processor.simulate_graph_by_resource_type_async(
                id_="1",
                graph_json=TWO_LINK_GRAPH,
                contained=False,
                max_concurrent_tasks=1,
                on_resource_type_completed=capture,
            )
        ]

    assert len(responses) == 3  # Patient, AllergyIntolerance, CarePlan

    # one event for the start resource (Patient) + one per link
    assert len(events) == 3
    assert events[0].resource_types == ["Patient"]
    assert events[0].graph_depth == 0
    assert events[0].link_index == -1
    assert {t for e in events[1:] for t in e.resource_types} == {
        "AllergyIntolerance",
        "CarePlan",
    }
    assert all(e.graph_depth == 0 for e in events[1:])
    # link_index correlates to each link's 0-based position in the graph
    # definition's link list (deterministic at max_concurrent_tasks=1).
    assert sorted(e.link_index for e in events[1:]) == [0, 1]


@pytest.mark.asyncio
async def test_on_resource_type_completed_defaults_to_none_is_noop() -> None:
    # No callback passed — must behave exactly as before (regression guard for
    # the "zero behavior change for existing callers" constraint).
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    with aioresponses() as m:
        mock_two_link_graph_responses(m)

        responses = [
            r
            async for r in graph_processor.simulate_graph_by_resource_type_async(
                id_="1",
                graph_json=TWO_LINK_GRAPH,
                contained=False,
                max_concurrent_tasks=1,
            )
        ]

    assert len(responses) == 3


@pytest.mark.asyncio
async def test_on_resource_type_completed_fires_correctly_at_concurrency_2() -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=2)

    events: list[ResourceTypeCompletionEvent] = []

    async def capture(event: ResourceTypeCompletionEvent) -> None:
        events.append(event)

    with aioresponses() as m:
        mock_two_link_graph_responses(m)

        async for _ in graph_processor.simulate_graph_by_resource_type_async(
            id_="1",
            graph_json=TWO_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=2,
            on_resource_type_completed=capture,
        ):
            pass

    # Regardless of which of the two links finishes first, each event's
    # resource_types must be internally consistent (no mixing of two links'
    # resource types into one event) and resource_count must match the sum of
    # that link's own chunks.
    non_start_events = [e for e in events if e.resource_types != ["Patient"]]
    all_reported_types = [t for e in non_start_events for t in e.resource_types]
    assert sorted(all_reported_types) == sorted(["AllergyIntolerance", "CarePlan"])


@pytest.mark.asyncio
async def test_full_event_lifecycle_fires_in_order_at_concurrency_1() -> None:
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

        responses = [
            r
            async for r in graph_processor.simulate_graph_by_resource_type_async(
                id_="1",
                graph_json=TWO_LINK_GRAPH,
                contained=False,
                max_concurrent_tasks=1,
                on_resource_type_started=on_started,
                on_resource_type_completed=on_completed,
                on_graph_retrieval_started=on_graph_started,
                on_graph_retrieval_completed=on_graph_completed,
            )
        ]

    assert len(responses) == 3  # Patient, AllergyIntolerance, CarePlan

    # exactly one graph-level bookend event each
    assert len(graph_started_events) == 1
    assert graph_started_events[0].start_resource_type == "Patient"
    assert graph_started_events[0].url == "http://example.com/fhir"

    assert len(graph_completed_events) == 1
    assert sorted(graph_completed_events[0].resource_types) == sorted(["Patient", "AllergyIntolerance", "CarePlan"])
    assert graph_completed_events[0].total_resource_count == 3
    assert graph_completed_events[0].max_graph_depth == 0
    assert sorted(graph_completed_events[0].urls) == sorted(
        [
            "http://example.com/fhir/Patient/1",
            "http://example.com/fhir/AllergyIntolerance?patient=1",
            "http://example.com/fhir/CarePlan?patient=1",
        ]
    )

    # one started + one completed per resource type (start resource + 2 links)
    assert len(started_events) == 3
    assert len(completed_events) == 3
    assert started_events[0].resource_types == ["Patient"]
    assert started_events[0].url == "http://example.com/fhir"
    assert started_events[0].link_index == -1
    assert completed_events[0].resource_types == ["Patient"]
    assert completed_events[0].urls == ["http://example.com/fhir/Patient/1"]
    assert completed_events[0].link_index == -1

    # at max_concurrent_tasks=1, ordering is fully deterministic: graph_started
    # fires before anything else, graph_completed fires after everything else,
    # and each resource type's started event fires immediately before its own
    # completed event (not interleaved with any other resource type's events).
    started_types_in_order = [e.resource_types[0] for e in started_events]
    completed_types_in_order = [e.resource_types[0] for e in completed_events]
    assert started_types_in_order == completed_types_in_order

    # the (graph_depth, link_index) correlation key pairs each started event
    # with its own completed event, for the start resource and every link.
    for started_event, completed_event in zip(started_events, completed_events, strict=True):
        assert started_event.graph_depth == completed_event.graph_depth
        assert started_event.link_index == completed_event.link_index
    # the two links get distinct, deterministic 0-based indices.
    assert sorted(e.link_index for e in started_events[1:]) == [0, 1]


@pytest.mark.asyncio
async def test_full_event_lifecycle_stays_correct_at_concurrency_2() -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=2)

    # A single shared timeline is required here (rather than four separate
    # lists) because `on_resource_type_started` fires from inside each row's
    # own concurrent task, while `on_resource_type_completed` fires from the
    # single-threaded outer generator loop. Comparing `list.index()` positions
    # across two separate lists cannot establish relative ordering between
    # them; only a single list that all callbacks append to, in the order
    # they actually run, can do that. Each entry is (kind, resource_type),
    # where kind is one of "graph_started", "started", "completed",
    # "graph_completed", and resource_type is the FHIR resource type for the
    # per-type events or a fixed marker for the whole-graph bookend events.
    timeline: list[tuple[str, str]] = []

    async def on_graph_started(event: GraphRetrievalStartedEvent) -> None:
        timeline.append(("graph_started", "__graph__"))

    async def on_started(event: ResourceTypeStartedEvent) -> None:
        timeline.append(("started", event.resource_types[0]))

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        timeline.append(("completed", event.resource_types[0]))

    async def on_graph_completed(event: GraphRetrievalCompletedEvent) -> None:
        timeline.append(("graph_completed", "__graph__"))

    with aioresponses() as m:
        mock_two_link_graph_responses(m)

        async for _ in graph_processor.simulate_graph_by_resource_type_async(
            id_="1",
            graph_json=TWO_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=2,
            on_resource_type_started=on_started,
            on_resource_type_completed=on_completed,
            on_graph_retrieval_started=on_graph_started,
            on_graph_retrieval_completed=on_graph_completed,
        ):
            pass

    resource_types = {"Patient", "AllergyIntolerance", "CarePlan"}

    # whole-graph bookends: each fires exactly once...
    graph_started_indices = [i for i, (kind, _) in enumerate(timeline) if kind == "graph_started"]
    graph_completed_indices = [i for i, (kind, _) in enumerate(timeline) if kind == "graph_completed"]
    assert len(graph_started_indices) == 1
    assert len(graph_completed_indices) == 1

    # ...and — since they fire outside the concurrent-rows section entirely —
    # sit at the very start and very end of the shared timeline, regardless of
    # how the concurrent per-row work interleaves in between.
    assert graph_started_indices[0] == 0
    assert graph_completed_indices[0] == len(timeline) - 1

    # every resource type produced exactly one started and one completed entry
    started_entries = [rt for kind, rt in timeline if kind == "started"]
    completed_entries = [rt for kind, rt in timeline if kind == "completed"]
    assert sorted(started_entries) == sorted(resource_types)
    assert sorted(completed_entries) == sorted(resource_types)

    # the narrower invariant that actually holds under concurrency: each
    # resource type's own "started" entry precedes that same type's own
    # "completed" entry in the shared timeline. We deliberately do NOT assert
    # any ordering between DIFFERENT resource types' started events, since
    # concurrent rows may legitimately interleave in either order.
    for resource_type in resource_types:
        first_started_index = next(
            i for i, (kind, rt) in enumerate(timeline) if kind == "started" and rt == resource_type
        )
        first_completed_index = next(
            i for i, (kind, rt) in enumerate(timeline) if kind == "completed" and rt == resource_type
        )
        assert first_started_index < first_completed_index


@pytest.mark.asyncio
async def test_graph_retrieval_completed_fires_on_zero_results() -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    graph_completed_events: list[GraphRetrievalCompletedEvent] = []

    async def on_graph_completed(event: GraphRetrievalCompletedEvent) -> None:
        graph_completed_events.append(event)

    with aioresponses() as m:
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Bundle", "entry": []},
        )

        responses = [
            r
            async for r in graph_processor.simulate_graph_by_resource_type_async(
                id_="1",
                graph_json=TWO_LINK_GRAPH,
                contained=False,
                max_concurrent_tasks=1,
                on_graph_retrieval_completed=on_graph_completed,
            )
        ]

    assert len(responses) == 1  # just the empty start-resource response
    assert len(graph_completed_events) == 1
    assert graph_completed_events[0].resource_types == []
    assert graph_completed_events[0].total_resource_count == 0
    assert graph_completed_events[0].max_graph_depth == 0


@pytest.mark.asyncio
async def test_on_resource_type_completed_fires_for_start_resource_with_zero_results() -> None:
    # Same gap as test_graph_retrieval_completed_fires_on_zero_results, but for
    # on_resource_type_completed specifically: the start resource's own
    # zero-result early-return path fires ResourceTypeStartedEvent but must
    # also fire a matching ResourceTypeCompletionEvent (Design Decision 3).
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    completed_events: list[ResourceTypeCompletionEvent] = []

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    with aioresponses() as m:
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Bundle", "entry": []},
        )

        responses = [
            r
            async for r in graph_processor.simulate_graph_by_resource_type_async(
                id_="1",
                graph_json=TWO_LINK_GRAPH,
                contained=False,
                max_concurrent_tasks=1,
                on_resource_type_completed=on_completed,
            )
        ]

    assert len(responses) == 1  # just the empty start-resource response
    assert len(completed_events) == 1
    assert completed_events[0].resource_types == ["Patient"]
    assert completed_events[0].resource_count == 0
    assert completed_events[0].graph_depth == 0
    assert completed_events[0].link_index == -1


@pytest.mark.asyncio
async def test_on_resource_type_completed_fires_with_declared_type_fallback_when_link_returns_nothing() -> None:
    # A path-based link (e.g. Patient.generalPractitioner) whose target
    # doesn't match anything on the parent resource is very common and must
    # still produce a completion event for the on_resource_type_started that
    # already fired for it (Design Decision 3), reporting the link's
    # *declared* target type with resource_count=0 — and this fallback must
    # NOT pollute the whole-graph aggregation, which only reflects resources
    # actually retrieved.
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
            # No "generalPractitioner" property, so the path-based link below
            # never matches any reference and yields zero resources.
            payload={"resourceType": "Patient", "id": "1"},
        )

        responses = [
            r
            async for r in graph_processor.simulate_graph_by_resource_type_async(
                id_="1",
                graph_json=PATH_LINK_GRAPH,
                contained=False,
                max_concurrent_tasks=1,
                on_resource_type_completed=on_completed,
                on_graph_retrieval_completed=on_graph_completed,
            )
        ]

    assert len(responses) == 1  # just the Patient; the link yielded nothing

    # one completion event for the start resource, one (fallback) for the link
    assert len(completed_events) == 2
    link_completed = completed_events[1]
    assert link_completed.resource_types == ["Practitioner"]  # declared-type fallback
    assert link_completed.resource_count == 0
    assert link_completed.graph_depth == 0
    assert link_completed.link_index == 0

    # the whole-graph aggregation is unaffected by the fallback: no
    # Practitioner was actually retrieved.
    assert len(graph_completed_events) == 1
    assert "Practitioner" not in graph_completed_events[0].resource_types
    assert graph_completed_events[0].total_resource_count == 1  # just Patient


def mock_nested_graph_responses(m: aioresponses) -> None:
    m.get(
        "http://example.com/fhir/Patient/1",
        payload={"resourceType": "Patient", "id": "1"},
    )
    m.get(
        "http://example.com/fhir/Encounter?patient=1",
        payload={"resourceType": "Encounter", "id": "10"},
    )
    m.get(
        "http://example.com/fhir/Practitioner?encounter=10",
        payload={"resourceType": "Practitioner", "id": "100"},
    )


@pytest.mark.asyncio
async def test_started_and_completed_events_fire_at_depth_1_for_nested_links() -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    started_events: list[ResourceTypeStartedEvent] = []
    completed_events: list[ResourceTypeCompletionEvent] = []

    async def on_started(event: ResourceTypeStartedEvent) -> None:
        started_events.append(event)

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    with aioresponses() as m:
        mock_nested_graph_responses(m)

        async for _ in graph_processor.simulate_graph_by_resource_type_async(
            id_="1",
            graph_json=NESTED_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
            on_resource_type_started=on_started,
            on_resource_type_completed=on_completed,
        ):
            pass

    depth_1_started = [e for e in started_events if e.graph_depth == 1]
    depth_1_completed = [e for e in completed_events if e.graph_depth == 1]
    assert len(depth_1_started) == 1
    assert depth_1_started[0].resource_types == ["Practitioner"]
    assert len(depth_1_completed) == 1
    assert depth_1_completed[0].resource_types == ["Practitioner"]
    assert depth_1_completed[0].resource_count == 1
    # the correlation key (graph_depth, link_index) pairs the depth-1
    # started event with its own depth-1 completed event.
    assert depth_1_started[0].link_index == depth_1_completed[0].link_index


@pytest.mark.asyncio
async def test_graph_retrieval_completed_fires_exactly_once_on_exception() -> None:
    # Design Decision 4: on_graph_retrieval_completed must fire exactly once
    # even when an exception propagates from inside the traversal — not
    # just on normal completion or the zero-results early return. Mock the
    # start-resource fetch to raise instead of returning a payload; the SDK
    # wraps whatever exception aiohttp/aioresponses raises into a
    # FhirSenderException as it propagates out of
    # _get_resources_by_parameters_async.
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
            async for _ in graph_processor.simulate_graph_by_resource_type_async(
                id_="1",
                graph_json=TWO_LINK_GRAPH,
                contained=False,
                max_concurrent_tasks=1,
                on_graph_retrieval_completed=on_graph_completed,
            ):
                pass

    assert len(graph_completed_events) == 1


@pytest.mark.asyncio
async def test_graph_retrieval_completed_fires_once_on_explicit_aclose() -> None:
    # Design Decision 4: on_graph_retrieval_completed must also fire when the
    # caller stops consuming the generator early via an explicit aclose()
    # (deterministic), as opposed to a bare `break` relied on to be
    # collected by the GC (explicitly out of scope — non-deterministic).
    #
    # This test calls _process_simulate_graph_by_resource_type_async
    # directly rather than the public simulate_graph_by_resource_type_async
    # wrapper. That public method is just
    # `async for r in self._process_simulate_graph_by_resource_type_async(...): yield r`
    # — a second, outer async generator. Closing that *outer* generator does
    # NOT deterministically close the inner one within the same await:
    # unwinding the outer generator's frame merely drops the inner
    # generator's refcount, and — because the inner generator is itself an
    # *unclosed* async generator at that point — finalizing it requires
    # asyncio's asyncgen finalizer hook, which only schedules aclose() on a
    # later event-loop turn rather than running it inline (verified
    # empirically: the inner generator's `finally` block did not run until
    # several `asyncio.sleep(0)` turns after the outer aclose() had already
    # returned). That delay is the same underlying non-determinism this test
    # deliberately avoids by not relying on the `break` path either.
    #
    # Calling aclose() directly on _process_simulate_graph_by_resource_type_async's
    # own generator object throws GeneratorExit straight into its own
    # suspended frame, which runs its `finally` block synchronously and
    # deterministically as part of this single aclose() call, since there is
    # no intervening wrapper generator to introduce that delay.
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    graph_completed_events: list[GraphRetrievalCompletedEvent] = []

    async def on_graph_completed(event: GraphRetrievalCompletedEvent) -> None:
        graph_completed_events.append(event)

    with aioresponses() as m:
        mock_two_link_graph_responses(m)

        agen = graph_processor._process_simulate_graph_by_resource_type_async(
            id_="1",
            graph_json=TWO_LINK_GRAPH,
            contained=False,
            logger=None,
            url="http://example.com/fhir",
            expand_fhir_bundle=None,
            auth_scopes=None,
            max_concurrent_tasks=1,
            sort_resources=None,
            on_graph_retrieval_completed=on_graph_completed,
        )

        # Advance past the first yield (the start resource, Patient) without
        # consuming the rest of the generator via `async for`.
        first_response = await agen.__anext__()
        assert first_response.resource_type == "Patient"

        # Explicitly close the generator early instead of exhausting it.
        await agen.aclose()

    assert len(graph_completed_events) == 1
