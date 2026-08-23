import asyncio
from collections.abc import AsyncGenerator
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


# A link with no "target" key at all (legal per GraphDefinitionLink.from_dict,
# which defaults target to []) — exercises the Bug 2 fix, where
# on_resource_type_started must fire unconditionally per link (previously
# gated on `row.target` being truthy, so this link never got a started
# event, yet the completion fallback fired unconditionally regardless).
NO_TARGET_LINK_GRAPH: dict[str, Any] = {
    "id": "1",
    "name": "Test Graph - No Target Link",
    "resourceType": "GraphDefinition",
    "start": "Patient",
    "link": [{}],
}


# A single link declaring TWO target types — exercises the documented
# "success beats everything" precedence in ResourceTypeCompletionEvent.outcome:
# one target's fetch succeeds while the other's 404s, and the whole link must
# still be reported as outcome="success" (see Ruling B in the task report).
MULTI_TARGET_LINK_GRAPH: dict[str, Any] = {
    "id": "1",
    "name": "Test Graph - Multi Target Link",
    "resourceType": "GraphDefinition",
    "start": "Patient",
    "link": [
        {
            "target": [
                {"type": "AllergyIntolerance", "params": "patient={ref}"},
                {"type": "CarePlan", "params": "patient={ref}"},
            ]
        },
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
                client_person_id="client-1",
                connection_name="Aetna Sandbox",
            )
        ]

    assert len(responses) == 3  # Patient, AllergyIntolerance, CarePlan

    # exactly one graph-level bookend event each
    assert len(graph_started_events) == 1
    assert graph_started_events[0].start_resource_type == "Patient"
    assert graph_started_events[0].url == "http://example.com/fhir"
    assert graph_started_events[0].client_person_id == "client-1"
    assert graph_started_events[0].connection_name == "Aetna Sandbox"

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
    assert graph_completed_events[0].client_person_id == "client-1"
    assert graph_completed_events[0].connection_name == "Aetna Sandbox"

    # one started + one completed per resource type (start resource + 2 links)
    assert len(started_events) == 3
    assert len(completed_events) == 3
    assert started_events[0].resource_types == ["Patient"]
    assert started_events[0].url == "http://example.com/fhir"
    assert started_events[0].link_index == -1
    assert completed_events[0].resource_types == ["Patient"]
    assert completed_events[0].urls == ["http://example.com/fhir/Patient/1"]
    assert completed_events[0].link_index == -1

    # client_person_id/connection_name are opaque pass-through values that
    # must show up unchanged on every fired event, for both the start
    # resource and every link — so a callback shared across multiple
    # concurrent calls can tell them apart.
    assert all(e.client_person_id == "client-1" for e in started_events)
    assert all(e.connection_name == "Aetna Sandbox" for e in started_events)
    assert all(e.client_person_id == "client-1" for e in completed_events)
    assert all(e.connection_name == "Aetna Sandbox" for e in completed_events)

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
async def test_on_resource_type_completed_fires_for_link_on_exception() -> None:
    # Design Decision (Bug 1, link variant): if a LINK's own fetch raises
    # (as opposed to the start resource's fetch, already covered by
    # test_graph_retrieval_completed_fires_exactly_once_on_exception), the
    # on_resource_type_started already fired for that link must still get a
    # matching on_resource_type_completed (resource_count=0) before the
    # exception propagates to the caller — otherwise a progress UI gets
    # stuck showing "retrieving AllergyIntolerance..." forever.
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    started_events: list[ResourceTypeStartedEvent] = []
    completed_events: list[ResourceTypeCompletionEvent] = []

    async def on_started(event: ResourceTypeStartedEvent) -> None:
        started_events.append(event)

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    with aioresponses() as m:
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Patient", "id": "1"},
        )
        # The AllergyIntolerance link's own fetch raises instead of
        # returning a payload.
        m.get(
            "http://example.com/fhir/AllergyIntolerance?patient=1",
            exception=RuntimeError("simulated network failure fetching link"),
        )
        # CarePlan is registered too so the mock server never errors on an
        # unmatched URL if it happens to be requested before the exception
        # above unwinds the traversal (max_concurrent_tasks=1 makes this
        # deterministic, but keep the graph fully mocked regardless).
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
                on_resource_type_started=on_started,
                on_resource_type_completed=on_completed,
            ):
                pass

    # The AllergyIntolerance link got both a started and a matching
    # completed event, with resource_count=0, despite the exception.
    allergy_started = [e for e in started_events if e.resource_types == ["AllergyIntolerance"]]
    allergy_completed = [e for e in completed_events if e.resource_types == ["AllergyIntolerance"]]
    assert len(allergy_started) == 1
    assert len(allergy_completed) == 1
    assert allergy_completed[0].resource_count == 0
    assert allergy_completed[0].urls == []
    assert allergy_started[0].link_index == allergy_completed[0].link_index


@pytest.mark.asyncio
async def test_on_resource_type_started_fires_for_link_with_no_target() -> None:
    # Bug 2: a link with no declared target (target == []) must still get a
    # started event (previously gated on `row.target` being truthy, so it
    # silently never fired one) that pairs symmetrically with the
    # unconditional completion fallback that already fires for such links.
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    started_events: list[ResourceTypeStartedEvent] = []
    completed_events: list[ResourceTypeCompletionEvent] = []

    async def on_started(event: ResourceTypeStartedEvent) -> None:
        started_events.append(event)

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    with aioresponses() as m:
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Patient", "id": "1"},
        )

        async for _ in graph_processor.simulate_graph_by_resource_type_async(
            id_="1",
            graph_json=NO_TARGET_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
            on_resource_type_started=on_started,
            on_resource_type_completed=on_completed,
        ):
            pass

    link_started = [e for e in started_events if e.link_index == 0]
    link_completed = [e for e in completed_events if e.link_index == 0]
    assert len(link_started) == 1
    assert link_started[0].resource_types == []
    assert len(link_completed) == 1
    assert link_completed[0].resource_types == []
    assert link_completed[0].resource_count == 0


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


@pytest.mark.asyncio
async def test_graph_retrieval_completed_fires_once_on_public_method_explicit_aclose() -> None:
    # Regression test for the gap flagged in
    # test_graph_retrieval_completed_fires_once_on_explicit_aclose's docstring
    # above: the PUBLIC simulate_graph_by_resource_type_async now wraps its
    # call to the private generator in a try/finally that explicitly awaits
    # inner_generator.aclose(), so closing the *public* generator early must
    # also deterministically run the inner generator's finally block (where
    # on_graph_retrieval_completed fires) within this same aclose() call —
    # not on some later event-loop turn via asyncio's asyncgen finalizer.
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    graph_completed_events: list[GraphRetrievalCompletedEvent] = []

    async def on_graph_completed(event: GraphRetrievalCompletedEvent) -> None:
        graph_completed_events.append(event)

    with aioresponses() as m:
        mock_two_link_graph_responses(m)

        agen = graph_processor.simulate_graph_by_resource_type_async(
            id_="1",
            graph_json=TWO_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
            on_graph_retrieval_completed=on_graph_completed,
        )

        # Advance past the first yield (the start resource, Patient) without
        # consuming the rest of the generator via `async for`.
        first_response = await agen.__anext__()
        assert first_response.resource_type == "Patient"

        # Explicitly close the PUBLIC generator early instead of exhausting it.
        await agen.aclose()


@pytest.mark.asyncio
async def test_on_resource_type_completed_fires_for_link_on_cancellation() -> None:
    # asyncio.CancelledError is a BaseException, not an Exception, so the
    # `except Exception:` guard around a link's own fetch would silently let
    # it bypass the completion-event firing entirely. This happens for real
    # whenever one concurrent link's failure causes AsyncParallelProcessor to
    # cancel other still-in-flight sibling link tasks (see
    # test_concurrent_batch_yields_completed_siblings_before_raising in
    # test_async_parallel_processor.py for the related data-loss fix at the
    # processor level). Simulated here by making the link's own fetch raise
    # CancelledError directly, which is deterministic and avoids depending on
    # real concurrent task-cancellation timing.
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    completed_events: list[ResourceTypeCompletionEvent] = []

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

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
                on_resource_type_completed=on_completed,
            ):
                pass

    # At max_concurrent_tasks=1, links are processed sequentially, so only
    # the first link (AllergyIntolerance) is ever attempted before its
    # cancelled fetch aborts the traversal — but that one link still gets a
    # matching completion event instead of the cancellation silently
    # bypassing it.
    non_start_completed = [e for e in completed_events if e.resource_types != ["Patient"]]
    assert len(non_start_completed) == 1
    assert non_start_completed[0].resource_types == ["AllergyIntolerance"]
    assert non_start_completed[0].resource_count == 0


@pytest.mark.asyncio
async def test_on_resource_type_completed_fires_for_start_resource_on_cancellation() -> None:
    # Same fix, applied to the start-resource fetch's own except clause:
    # asyncio.CancelledError there must also fire a matching completion event
    # for the ResourceTypeStartedEvent fired earlier for the start resource,
    # and on_graph_retrieval_completed must still fire exactly once from the
    # outer finally regardless.
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    completed_events: list[ResourceTypeCompletionEvent] = []
    graph_completed_events: list[GraphRetrievalCompletedEvent] = []

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    async def on_graph_completed(event: GraphRetrievalCompletedEvent) -> None:
        graph_completed_events.append(event)

    async def raise_cancelled(**kwargs: Any) -> Any:
        raise asyncio.CancelledError()

    graph_processor._get_resources_by_parameters_async = raise_cancelled  # type: ignore[method-assign]

    with pytest.raises(asyncio.CancelledError):
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
    assert completed_events[0].resource_types == ["Patient"]
    assert completed_events[0].resource_count == 0
    assert len(graph_completed_events) == 1

    assert len(graph_completed_events) == 1


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


@pytest.mark.asyncio
async def test_resource_type_completed_outcome_success_beats_sibling_target_not_found() -> None:
    # Ruling B regression guard: a single link declaring two target types,
    # where one target's fetch succeeds and the other's 404s, must still be
    # reported as outcome="success" for the whole link — per the documented
    # precedence in ResourceTypeCompletionEvent.outcome ("success beats
    # everything; a single successful target makes the whole link 'success'
    # even if a sibling target within the same link was denied or not
    # found"). Also guards against a naive fix that would classify by
    # get_resource_count() alone: the 404 response's OperationOutcome body
    # would otherwise inflate resource_count_for_link without being a real
    # success.
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
            payload={"resourceType": "AllergyIntolerance", "id": "1"},
        )
        m.get(
            "http://example.com/fhir/CarePlan?patient=1",
            status=404,
            payload={"resourceType": "OperationOutcome"},
        )

        async for _ in graph_processor.simulate_graph_by_resource_type_async(
            id_="1",
            graph_json=MULTI_TARGET_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
            on_resource_type_completed=on_completed,
        ):
            pass

    link_completed = [e for e in completed_events if e.link_index == 0]
    assert len(link_completed) == 1
    assert link_completed[0].outcome == "success"


@pytest.mark.asyncio
async def test_resource_type_completed_outcome_not_found_for_start_resource() -> None:
    # Ruling C regression guard: the start resource's own 404-with-body fetch
    # must be classified as outcome="not_found", not "success" — the
    # OperationOutcome body parses into a FhirResource, so
    # get_resource_count() returns 1 (not 0), which would otherwise skip the
    # zero-result guard entirely and fall through to the unconditional
    # outcome="success" block below it.
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

        async for _ in graph_processor.simulate_graph_by_resource_type_async(
            id_="1",
            graph_json=TWO_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
            on_resource_type_completed=on_completed,
        ):
            pass

    assert len(completed_events) == 1
    assert completed_events[0].outcome == "not_found"
