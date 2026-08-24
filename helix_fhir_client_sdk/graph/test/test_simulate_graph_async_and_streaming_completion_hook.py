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

# NESTED_GRAPH: Patient -> Encounter (depth 0) -> Practitioner (depth 1).
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
    # that is what this test actually proves.
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
            on_graph_retrieval_completed=on_graph_completed,
        )

    assert len(completed_events) == 1
    assert completed_events[0].resource_types == ["Patient"]
    assert completed_events[0].outcome == "not_found"

    # A 404-with-OperationOutcome-body start response must not be reported
    # as a successfully-retrieved Patient in the whole-graph rollups.
    assert len(graph_completed_events) == 1
    assert graph_completed_events[0].resource_types == []
    assert graph_completed_events[0].total_resource_count == 0


@pytest.mark.asyncio
@USE_STREAMING_PARAMS
async def test_not_found_start_resource_skips_link_traversal(use_streaming: bool) -> None:
    # DCON-5260: process_simulate_graph_async()'s early-return branch used
    # to check the raw get_resource_count() (which counts the
    # OperationOutcome placeholder), so a 404 start resource fell through
    # to link traversal against that bogus entry instead of stopping, like
    # _process_simulate_graph_by_resource_type_async() already does. No
    # AllergyIntolerance/CarePlan endpoint is mocked below — if the
    # traversal wrongly proceeds, aioresponses raises for the unmatched
    # request and this test fails.
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    with aioresponses() as m:
        m.get(
            "http://example.com/fhir/Patient/1",
            status=404,
            payload={"resourceType": "OperationOutcome"},
        )

        responses = await call_graph_method(
            graph_processor,
            use_streaming=use_streaming,
            id_="1",
            graph_json=TWO_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
        )

    assert len(responses) == 1
    assert [resource.get("resourceType") for resource in responses[0].get_resources()] == ["OperationOutcome"]


@pytest.mark.asyncio
@USE_STREAMING_PARAMS
async def test_resource_type_completed_outcome_scope_denied_for_start_resource(use_streaming: bool) -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)
    graph_processor._auth_scopes = ["patient/CarePlan.read"]

    completed_events: list[ResourceTypeCompletionEvent] = []
    graph_completed_events: list[GraphRetrievalCompletedEvent] = []

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    async def on_graph_completed(event: GraphRetrievalCompletedEvent) -> None:
        graph_completed_events.append(event)

    with aioresponses():
        # No Patient/AllergyIntolerance/CarePlan endpoint is mocked at all —
        # the scope denial must short-circuit before any HTTP call.
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

    assert len(completed_events) == 1
    assert completed_events[0].outcome == "scope_denied"
    assert len(graph_completed_events) == 1
    assert graph_completed_events[0].total_rejected_count == 1
    assert graph_completed_events[0].total_error_count == 0


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


@pytest.mark.asyncio
async def test_graph_retrieval_completed_fires_once_on_streaming_explicit_aclose() -> None:
    # simulate_graph_streaming_async() wraps process_simulate_graph_async() in a
    # try/finally that explicitly awaits inner_generator.aclose() — this proves
    # that wrapper actually does something: closing the PUBLIC generator early
    # must still deterministically fire on_graph_retrieval_completed within this
    # same aclose() call, not on some later event-loop turn.
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    graph_completed_events: list[GraphRetrievalCompletedEvent] = []

    async def on_graph_completed(event: GraphRetrievalCompletedEvent) -> None:
        graph_completed_events.append(event)

    with aioresponses() as m:
        mock_two_link_graph_responses(m)

        agen = graph_processor.simulate_graph_streaming_async(
            id_="1",
            graph_json=TWO_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
            on_graph_retrieval_completed=on_graph_completed,
        )

        # Advance past the first (only) yield without exhausting the generator
        # via `async for`.
        first_response = await agen.__anext__()
        assert first_response.get_resource_count() == 3

        # Explicitly close the PUBLIC generator early instead of exhausting it.
        await agen.aclose()

    assert len(graph_completed_events) == 1


@pytest.mark.asyncio
@USE_STREAMING_PARAMS
async def test_started_and_completed_events_fire_at_depth_1_for_nested_links(use_streaming: bool) -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    started_events: list[ResourceTypeStartedEvent] = []
    completed_events: list[ResourceTypeCompletionEvent] = []
    graph_completed_events: list[GraphRetrievalCompletedEvent] = []

    async def on_started(event: ResourceTypeStartedEvent) -> None:
        started_events.append(event)

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
            "http://example.com/fhir/Encounter?patient=1",
            payload={"resourceType": "Encounter", "id": "10"},
        )
        m.get(
            "http://example.com/fhir/Practitioner?encounter=10",
            payload={"resourceType": "Practitioner", "id": "100"},
        )

        responses = await call_graph_method(
            graph_processor,
            use_streaming=use_streaming,
            id_="1",
            graph_json=NESTED_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
            on_resource_type_started=on_started,
            on_resource_type_completed=on_completed,
            on_graph_retrieval_completed=on_graph_completed,
        )

    assert len(responses) == 1
    assert responses[0].get_resource_count() == 3  # Patient, Encounter, Practitioner

    depth_1_started = [e for e in started_events if e.graph_depth == 1]
    depth_1_completed = [e for e in completed_events if e.graph_depth == 1]
    assert len(depth_1_started) == 1
    assert depth_1_started[0].resource_types == ["Practitioner"]
    assert len(depth_1_completed) == 1
    assert depth_1_completed[0].resource_types == ["Practitioner"]
    assert depth_1_completed[0].outcome == "success"

    assert len(graph_completed_events) == 1
    assert graph_completed_events[0].max_graph_depth == 1
    assert graph_completed_events[0].total_resource_count == 3


@pytest.mark.asyncio
@USE_STREAMING_PARAMS
async def test_start_resource_partial_multi_id_fetch_is_not_dropped(use_streaming: bool) -> None:
    # Regression guard (PR review finding): FhirGetResponse.append() never
    # recomputes `status`, so an aggregated multi-id start-resource response
    # (the ?_id=1,2 search failed, forcing the one-by-one fallback) inherits
    # whichever sub-fetch's status landed first. Here id "1" 404s and id "2"
    # succeeds, so the aggregated response reports successful == False /
    # status == 404 while actually carrying a real Patient. Classifying
    # start_resource_outcome from .status/.successful alone would wrongly
    # report "not_found" and skip adding the real data to the whole-graph
    # rollups — the classification must be content-based instead (mirroring
    # _process_simulate_graph_by_resource_type_async's own
    # real_parent_resource_count check), independent of this method's
    # unchanged raw-count branching.
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    completed_events: list[ResourceTypeCompletionEvent] = []
    graph_completed_events: list[GraphRetrievalCompletedEvent] = []

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    async def on_graph_completed(event: GraphRetrievalCompletedEvent) -> None:
        graph_completed_events.append(event)

    with aioresponses() as m:
        # The combined _id search fails, which is what triggers the SDK's
        # one-by-one fallback for the remaining ids.
        m.get(
            "http://example.com/fhir/Patient?_id=1,2",
            status=400,
            payload={"resourceType": "OperationOutcome"},
        )
        m.get(
            "http://example.com/fhir/Patient/1",
            status=404,
            payload={"resourceType": "OperationOutcome"},
        )
        m.get(
            "http://example.com/fhir/Patient/2",
            payload={"resourceType": "Patient", "id": "2"},
        )
        m.get(
            "http://example.com/fhir/AllergyIntolerance?patient=2",
            payload={"resourceType": "AllergyIntolerance", "id": "1"},
        )
        m.get(
            "http://example.com/fhir/CarePlan?patient=2",
            payload={"resourceType": "CarePlan", "id": "1"},
        )

        responses = await call_graph_method(
            graph_processor,
            use_streaming=use_streaming,
            id_=["1", "2"],
            graph_json=TWO_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
            on_resource_type_completed=on_completed,
            on_graph_retrieval_completed=on_graph_completed,
        )

    # The real Patient that was successfully fetched one-by-one survived,
    # and the traversal was NOT aborted — both links ran off it. The merged
    # response also still holds the id "1" 404's OperationOutcome entry
    # (get_resource_count() counts it too) — that's pre-existing,
    # unrelated behavior; the fix under test is the outcome *classification*,
    # not what ends up in the merged bundle.
    assert len(responses) == 1
    patient_resources = [
        resource for resource in responses[0].get_resources() if resource.get("resourceType") == "Patient"
    ]
    assert [resource.get("id") for resource in patient_resources] == ["2"]
    assert sorted(
        resource["resourceType"] for resource in responses[0].get_resources() if resource.get("resourceType")
    ) == ["AllergyIntolerance", "CarePlan", "OperationOutcome", "Patient"]

    # The start resource's completion event is classified "success", not
    # "not_found" — and the whole-graph rollups reflect the real data.
    start_completed = [e for e in completed_events if e.link_index == -1]
    assert len(start_completed) == 1
    assert start_completed[0].outcome == "success"
    assert start_completed[0].error_type is None
    assert start_completed[0].error_message is None

    assert len(graph_completed_events) == 1
    assert "Patient" in graph_completed_events[0].resource_types
    assert graph_completed_events[0].total_error_count == 0
