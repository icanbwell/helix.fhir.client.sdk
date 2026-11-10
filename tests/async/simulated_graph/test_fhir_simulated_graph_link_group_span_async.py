"""DCON-6541: the graph traversal starts one span fhir.client_sdk.graph.link_group for each link group.

A link group is the list of links that the traversal runs for one set of parent resources: at depth 0 the links of the
start resource, and at the next depth the links of each target that has nested links. The groups of a depth run one
after the other. The span has the depth, the group index, the link count and the child GET count, and no URLs and no
ids.

aioresponses mocks the FHIR server (the HTTP boundary); SpanRecorder (tests/span_recorder.py) records the spans. The
names of the span and of its attributes are literals here, because dashboards and queries use them.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import pytest
from aioresponses import CallbackResult, aioresponses
from opentelemetry.trace import StatusCode
from yarl import URL

from helix_fhir_client_sdk.exceptions.fhir_sender_exception import FhirSenderException
from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.graph import simulated_graph_processor_mixin
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from tests.span_recorder import RecordedSpan, SpanRecorder

BASE_URL = "http://fhir.example.test/4_0_0"
PATIENT_ID = "patient-test-001"

LINK_GROUP_SPAN = "fhir.client_sdk.graph.link_group"
DEPTH = "fhir.client_sdk.graph.depth"
GROUP_INDEX = "fhir.client_sdk.graph.link_group.index"
LINK_COUNT = "fhir.client_sdk.graph.link.count"
CHILD_GET_COUNT = "fhir.client_sdk.graph.child_get.count"

PATIENT: dict[str, Any] = {"resourceType": "Patient", "id": PATIENT_ID}


def _search_result(*resources: dict[str, Any], next_page: str | None = None) -> dict[str, Any]:
    """Returns a search Bundle with the resources, and a link to the next page if next_page is set."""
    bundle: dict[str, Any] = {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [{"resource": resource} for resource in resources],
    }
    if next_page:
        bundle["link"] = [{"relation": "next", "url": f"{BASE_URL}/{next_page}"}]
    return bundle


@dataclass(frozen=True)
class GraphShape:
    """A graph, the answers of the mock FHIR server, and what the traversal of the graph does."""

    name: str
    graph: dict[str, Any]
    # the path and query of each request (after BASE_URL), and the JSON that answers it
    answers: dict[str, dict[str, Any]]
    # the requests, in the order that the traversal sends them when it runs one task at a time
    requests: list[str]
    # "resourceType/id" of each resource that the traversal returns, sorted
    resources: list[str]
    # (depth, group index, link count, child GET count) of each link group, in the order that the groups run
    link_groups: list[tuple[int, int, int, int]]


ONE_GROUP = GraphShape(
    name="one-group",
    graph={
        "resourceType": "GraphDefinition",
        "id": "link-group-span-one-group",
        "name": "link_group_span_one_group",
        "start": "Patient",
        "link": [
            {"target": [{"type": "Condition", "params": "patient={ref}"}]},
            {"target": [{"type": "Observation", "params": "patient={ref}"}]},
        ],
    },
    answers={
        f"Patient/{PATIENT_ID}": PATIENT,
        f"Condition?patient={PATIENT_ID}": _search_result({"resourceType": "Condition", "id": "condition-test-001"}),
        # two pages: each page is one GET request
        f"Observation?patient={PATIENT_ID}": _search_result(
            {"resourceType": "Observation", "id": "observation-test-001"},
            next_page=f"Observation?patient={PATIENT_ID}&_getpagesoffset=1",
        ),
        f"Observation?patient={PATIENT_ID}&_getpagesoffset=1": _search_result(
            {"resourceType": "Observation", "id": "observation-test-002"}
        ),
    },
    requests=[
        f"Patient/{PATIENT_ID}",
        f"Condition?patient={PATIENT_ID}",
        f"Observation?patient={PATIENT_ID}",
        f"Observation?patient={PATIENT_ID}&_getpagesoffset=1",
    ],
    resources=[
        "Condition/condition-test-001",
        "Observation/observation-test-001",
        "Observation/observation-test-002",
        f"Patient/{PATIENT_ID}",
    ],
    link_groups=[(0, 0, 2, 3)],
)

# one group at depth 0 (Encounter, Procedure), and two groups at depth 1 that run one after the other: the links of
# Encounter (serviceProvider, Observation) and the link of Procedure (encounter)
THREE_GROUPS = GraphShape(
    name="three-groups",
    graph={
        "resourceType": "GraphDefinition",
        "id": "link-group-span-three-groups",
        "name": "link_group_span_three_groups",
        "start": "Patient",
        "link": [
            {
                "target": [
                    {
                        "type": "Encounter",
                        "params": "patient={ref}",
                        "link": [
                            {"path": "serviceProvider", "target": [{"type": "Organization"}]},
                            {"target": [{"type": "Observation", "params": "encounter={ref}"}]},
                        ],
                    }
                ]
            },
            {
                "target": [
                    {
                        "type": "Procedure",
                        "params": "patient={ref}",
                        "link": [{"path": "encounter", "target": [{"type": "Encounter"}]}],
                    }
                ]
            },
        ],
    },
    answers={
        f"Patient/{PATIENT_ID}": PATIENT,
        f"Encounter?patient={PATIENT_ID}": _search_result(
            {
                "resourceType": "Encounter",
                "id": "encounter-test-001",
                "serviceProvider": {"reference": "Organization/organization-test-001"},
            },
            {
                "resourceType": "Encounter",
                "id": "encounter-test-002",
                "serviceProvider": {"reference": "Organization/organization-test-002"},
            },
        ),
        f"Procedure?patient={PATIENT_ID}": _search_result(
            {
                "resourceType": "Procedure",
                "id": "procedure-test-001",
                "encounter": {"reference": "Encounter/encounter-test-001"},
            }
        ),
        "Organization/organization-test-001": {"resourceType": "Organization", "id": "organization-test-001"},
        "Organization/organization-test-002": {"resourceType": "Organization", "id": "organization-test-002"},
        "Observation?encounter=encounter-test-001": _search_result(
            {"resourceType": "Observation", "id": "observation-test-001"}
        ),
        "Observation?encounter=encounter-test-002": _search_result(
            {"resourceType": "Observation", "id": "observation-test-002"}
        ),
    },
    requests=[
        f"Patient/{PATIENT_ID}",
        f"Encounter?patient={PATIENT_ID}",
        f"Procedure?patient={PATIENT_ID}",
        "Organization/organization-test-001",
        "Organization/organization-test-002",
        "Observation?encounter=encounter-test-001",
        "Observation?encounter=encounter-test-002",
    ],
    resources=[
        "Encounter/encounter-test-001",
        "Encounter/encounter-test-002",
        "Observation/observation-test-001",
        "Observation/observation-test-002",
        "Organization/organization-test-001",
        "Organization/organization-test-002",
        f"Patient/{PATIENT_ID}",
        "Procedure/procedure-test-001",
    ],
    # the encounter of the procedure is in the cache already, so the last group sends no GET request
    link_groups=[(0, 0, 2, 2), (1, 0, 2, 4), (1, 1, 1, 0)],
)

DEPTH_TWO = GraphShape(
    name="depth-2",
    graph={
        "resourceType": "GraphDefinition",
        "id": "link-group-span-depth-2",
        "name": "link_group_span_depth_2",
        "start": "Patient",
        "link": [
            {
                "target": [
                    {
                        "type": "Encounter",
                        "params": "patient={ref}",
                        "link": [
                            {
                                "path": "serviceProvider",
                                "target": [
                                    {
                                        "type": "Organization",
                                        "link": [{"path": "partOf", "target": [{"type": "Organization"}]}],
                                    }
                                ],
                            }
                        ],
                    }
                ]
            },
            {"target": [{"type": "Condition", "params": "patient={ref}"}]},
        ],
    },
    answers={
        f"Patient/{PATIENT_ID}": PATIENT,
        f"Encounter?patient={PATIENT_ID}": _search_result(
            {
                "resourceType": "Encounter",
                "id": "encounter-test-001",
                "serviceProvider": {"reference": "Organization/organization-test-001"},
            }
        ),
        f"Condition?patient={PATIENT_ID}": _search_result({"resourceType": "Condition", "id": "condition-test-001"}),
        "Organization/organization-test-001": {
            "resourceType": "Organization",
            "id": "organization-test-001",
            "partOf": {"reference": "Organization/organization-test-002"},
        },
        "Organization/organization-test-002": {"resourceType": "Organization", "id": "organization-test-002"},
    },
    requests=[
        f"Patient/{PATIENT_ID}",
        f"Encounter?patient={PATIENT_ID}",
        f"Condition?patient={PATIENT_ID}",
        "Organization/organization-test-001",
        "Organization/organization-test-002",
    ],
    resources=[
        "Condition/condition-test-001",
        "Encounter/encounter-test-001",
        "Organization/organization-test-001",
        "Organization/organization-test-002",
        f"Patient/{PATIENT_ID}",
    ],
    link_groups=[(0, 0, 2, 2), (1, 0, 1, 1), (2, 0, 1, 1)],
)

SHAPES = [ONE_GROUP, THREE_GROUPS, DEPTH_TWO]

# the first GET request of the second group of THREE_GROUPS (depth 1, index 0)
FAILING_CHILD_GET = "Organization/organization-test-001"


@dataclass
class MockFhirServer:
    """Answers GET requests with fixed JSON, and keeps the path and query of each request in order."""

    answers: dict[str, dict[str, Any]]
    # the number of times that a path answers with status 500 before it answers with its JSON
    failures: dict[str, int] = field(default_factory=dict)
    requests: list[str] = field(default_factory=list)

    def install(self, fhir_server: aioresponses) -> None:
        for path in self.answers:
            fhir_server.get(f"{BASE_URL}/{path}", callback=self._answer_for(path=path), repeat=True)

    def _answer_for(self, *, path: str) -> Callable[..., CallbackResult]:
        def answer(url: URL, **kwargs: Any) -> CallbackResult:
            self.requests.append(path)
            if self.requests.count(path) <= self.failures.get(path, 0):
                return CallbackResult(status=500)
            return CallbackResult(status=200, payload=self.answers[path])

        return answer


async def _simulate_graph(
    fhir_client: FhirClient, graph: dict[str, Any], max_concurrent_tasks: int, continue_on_error: bool
) -> list[FhirGetResponse]:
    response = await fhir_client.simulate_graph_async(
        id_=PATIENT_ID,
        graph_json=graph,
        contained=False,
        max_concurrent_tasks=max_concurrent_tasks,
        continue_on_resource_type_error=continue_on_error,
    )
    return [response]


async def _simulate_graph_streaming(
    fhir_client: FhirClient, graph: dict[str, Any], max_concurrent_tasks: int, continue_on_error: bool
) -> list[FhirGetResponse]:
    return [
        response
        async for response in fhir_client.simulate_graph_streaming_async(
            id_=PATIENT_ID,
            graph_json=graph,
            contained=False,
            max_concurrent_tasks=max_concurrent_tasks,
            continue_on_resource_type_error=continue_on_error,
        )
    ]


async def _simulate_graph_by_resource_type(
    fhir_client: FhirClient, graph: dict[str, Any], max_concurrent_tasks: int, continue_on_error: bool
) -> list[FhirGetResponse]:
    return [
        response
        async for response in fhir_client.simulate_graph_by_resource_type_async(
            id_=PATIENT_ID,
            graph_json=graph,
            contained=False,
            max_concurrent_tasks=max_concurrent_tasks,
            continue_on_resource_type_error=continue_on_error,
        )
    ]


@dataclass(frozen=True)
class Traversal:
    """A public method of FhirClient that traverses a graph."""

    name: str
    run: Callable[[FhirClient, dict[str, Any], int, bool], Awaitable[list[FhirGetResponse]]]


TRAVERSALS = [
    Traversal("simulate_graph_async", _simulate_graph),
    Traversal("simulate_graph_streaming_async", _simulate_graph_streaming),
    Traversal("simulate_graph_by_resource_type_async", _simulate_graph_by_resource_type),
]


def _resource_keys(responses: list[FhirGetResponse]) -> list[str]:
    """Returns "resourceType/id" of each resource in the responses, sorted."""
    return sorted(
        f"{entry.resource.get('resourceType')}/{entry.resource.get('id')}"
        for response in responses
        for entry in response.get_bundle_entries()
        if entry.resource is not None
    )


def _link_groups(spans: list[RecordedSpan]) -> list[tuple[int, int, int, int]]:
    """Returns (depth, group index, link count, child GET count) of each span, in the order that the spans started."""
    return [
        (
            span.attributes[DEPTH],
            span.attributes[GROUP_INDEX],
            span.attributes[LINK_COUNT],
            span.attributes[CHILD_GET_COUNT],
        )
        for span in spans
    ]


def _keep_the_default_tracer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keeps the tracer of the traversal. This package has no OpenTelemetry SDK, so the tracer records nothing."""


def _record_the_spans(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(simulated_graph_processor_mixin, "TRACER", SpanRecorder())


@pytest.fixture
def span_recorder(monkeypatch: pytest.MonkeyPatch) -> SpanRecorder:
    """Records the spans that the graph traversal starts."""
    recorder = SpanRecorder()
    monkeypatch.setattr(simulated_graph_processor_mixin, "TRACER", recorder)
    return recorder


@pytest.mark.parametrize(
    "use_tracer", [_keep_the_default_tracer, _record_the_spans], ids=["no-op-tracer", "recording-tracer"]
)
@pytest.mark.parametrize("shape", SHAPES, ids=[shape.name for shape in SHAPES])
@pytest.mark.parametrize("traversal", TRAVERSALS, ids=[traversal.name for traversal in TRAVERSALS])
async def test_traversal_returns_the_same_resources_and_sends_the_same_requests(
    traversal: Traversal,
    shape: GraphShape,
    use_tracer: Callable[[pytest.MonkeyPatch], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    use_tracer(monkeypatch)
    fhir_server = MockFhirServer(answers=shape.answers)

    # Act
    with aioresponses() as mocked_fhir_server:
        fhir_server.install(mocked_fhir_server)
        responses = await traversal.run(FhirClient().url(BASE_URL), shape.graph, 1, False)

    # Assert
    assert _resource_keys(responses) == shape.resources
    assert fhir_server.requests == shape.requests


@pytest.mark.parametrize("shape", SHAPES, ids=[shape.name for shape in SHAPES])
@pytest.mark.parametrize("traversal", TRAVERSALS, ids=[traversal.name for traversal in TRAVERSALS])
async def test_one_link_group_span_per_link_group(
    traversal: Traversal, shape: GraphShape, span_recorder: SpanRecorder
) -> None:
    # Arrange
    fhir_server = MockFhirServer(answers=shape.answers)

    # Act
    with aioresponses() as mocked_fhir_server:
        fhir_server.install(mocked_fhir_server)
        await traversal.run(FhirClient().url(BASE_URL), shape.graph, 1, False)

    # Assert
    spans = span_recorder.spans_named(LINK_GROUP_SPAN)
    assert _link_groups(spans) == shape.link_groups
    assert all(span.ended for span in spans)
    assert [span.status.status_code for span in spans] == [StatusCode.UNSET] * len(spans)
    # the first request gets the start resource; each other request is a child GET of one group
    assert sum(span.attributes[CHILD_GET_COUNT] for span in spans) == len(fhir_server.requests) - 1


@pytest.mark.parametrize("shape", SHAPES, ids=[shape.name for shape in SHAPES])
@pytest.mark.parametrize("traversal", TRAVERSALS, ids=[traversal.name for traversal in TRAVERSALS])
async def test_child_get_counts_are_correct_when_the_links_run_concurrently(
    traversal: Traversal, shape: GraphShape, span_recorder: SpanRecorder
) -> None:
    # Arrange
    fhir_server = MockFhirServer(answers=shape.answers)

    # Act
    with aioresponses() as mocked_fhir_server:
        fhir_server.install(mocked_fhir_server)
        await traversal.run(FhirClient().url(BASE_URL), shape.graph, 4, False)

    # Assert
    # the groups of a depth can finish in any order, so the order of the groups and their indexes can change
    spans = span_recorder.spans_named(LINK_GROUP_SPAN)
    actual_groups = _link_groups(spans)
    assert sorted((depth, links, gets) for depth, _, links, gets in actual_groups) == sorted(
        (depth, links, gets) for depth, _, links, gets in shape.link_groups
    )
    assert sorted((depth, index) for depth, index, _, _ in actual_groups) == sorted(
        (depth, index) for depth, index, _, _ in shape.link_groups
    )
    assert sum(span.attributes[CHILD_GET_COUNT] for span in spans) == len(fhir_server.requests) - 1


@pytest.mark.parametrize("shape", SHAPES, ids=[shape.name for shape in SHAPES])
@pytest.mark.parametrize("traversal", TRAVERSALS, ids=[traversal.name for traversal in TRAVERSALS])
async def test_link_group_span_has_no_identifier_and_no_url(
    traversal: Traversal, shape: GraphShape, span_recorder: SpanRecorder
) -> None:
    # Arrange
    fhir_server = MockFhirServer(answers=shape.answers)
    identifiers = [resource.split("/")[1] for resource in shape.resources]
    url_parts = ["fhir.example.test", "http", "/", "?", "="]

    # Act
    with aioresponses() as mocked_fhir_server:
        fhir_server.install(mocked_fhir_server)
        await traversal.run(FhirClient().url(BASE_URL), shape.graph, 1, False)

    # Assert
    spans = span_recorder.spans_named(LINK_GROUP_SPAN)
    assert spans
    for span in spans:
        assert set(span.attributes) == {DEPTH, GROUP_INDEX, LINK_COUNT, CHILD_GET_COUNT}
        assert all(type(value) is int for value in span.attributes.values())
        for text in span.recorded_texts():
            assert not [value for value in identifiers + url_parts if value in text]


@pytest.mark.parametrize("traversal", TRAVERSALS, ids=[traversal.name for traversal in TRAVERSALS])
async def test_failing_child_get_that_stops_the_traversal_sets_a_type_only_error_status(
    traversal: Traversal, span_recorder: SpanRecorder
) -> None:
    # Arrange
    fhir_server = MockFhirServer(answers=THREE_GROUPS.answers, failures={FAILING_CHILD_GET: 1})
    fhir_client = FhirClient().url(BASE_URL).retry_count(0)

    # Act
    with aioresponses() as mocked_fhir_server:
        fhir_server.install(mocked_fhir_server)
        with pytest.raises(FhirSenderException):
            await traversal.run(fhir_client, THREE_GROUPS.graph, 1, False)

    # Assert
    spans = span_recorder.spans_named(LINK_GROUP_SPAN)
    [depth_0_group, failing_group] = spans
    assert _link_groups([failing_group])[0][:2] == (1, 0)
    assert failing_group.status.status_code == StatusCode.ERROR
    assert failing_group.status.description == "FhirSenderException"
    assert failing_group.events == []
    assert depth_0_group.status.status_code == StatusCode.UNSET
    assert all(span.ended for span in spans)


@pytest.mark.parametrize("traversal", TRAVERSALS, ids=[traversal.name for traversal in TRAVERSALS])
async def test_failing_child_get_that_the_traversal_continues_past_sets_a_type_only_error_status(
    traversal: Traversal, span_recorder: SpanRecorder
) -> None:
    # Arrange
    fhir_server = MockFhirServer(answers=THREE_GROUPS.answers, failures={FAILING_CHILD_GET: 1})
    fhir_client = FhirClient().url(BASE_URL).retry_count(0)

    # Act
    with aioresponses() as mocked_fhir_server:
        fhir_server.install(mocked_fhir_server)
        await traversal.run(fhir_client, THREE_GROUPS.graph, 1, True)

    # Assert
    spans = span_recorder.spans_named(LINK_GROUP_SPAN)
    [depth_0_group, failing_group, last_group] = spans
    assert _link_groups([failing_group])[0][:2] == (1, 0)
    assert failing_group.status.status_code == StatusCode.ERROR
    assert failing_group.status.description == "FhirSenderException"
    assert failing_group.events == []
    assert [depth_0_group.status.status_code, last_group.status.status_code] == [StatusCode.UNSET] * 2
    assert all(span.ended for span in spans)


async def test_closing_the_traversal_inside_a_group_ends_the_link_group_span_without_an_error(
    span_recorder: SpanRecorder,
) -> None:
    # Arrange
    # only simulate_graph_by_resource_type_async yields to its caller inside a link group
    fhir_server = MockFhirServer(answers=THREE_GROUPS.answers)
    fhir_client = FhirClient().url(BASE_URL)

    # Act
    with aioresponses() as mocked_fhir_server:
        fhir_server.install(mocked_fhir_server)
        stream = fhir_client.simulate_graph_by_resource_type_async(
            id_=PATIENT_ID, graph_json=THREE_GROUPS.graph, contained=False, max_concurrent_tasks=1
        )
        # the start resource, then the response of the first link of the depth 0 group
        await anext(stream)
        await anext(stream)
        await stream.aclose()

    # Assert
    [open_group] = span_recorder.spans_named(LINK_GROUP_SPAN)
    assert _link_groups([open_group]) == [(0, 0, 2, 1)]
    assert open_group.ended
    assert open_group.status.status_code == StatusCode.UNSET
    assert open_group.events == []


def test_link_group_span_of_a_client_without_a_request_counter_ends_and_keeps_the_error(
    span_recorder: SpanRecorder,
) -> None:
    # Arrange
    # as for a class that mixes in the traversal without running RequestQueueMixin.__init__
    fhir_client = FhirClient()
    del fhir_client._sent_request_count

    # Act
    with (
        pytest.raises(ValueError, match="^synthetic failure$"),
        fhir_client._link_group_span(graph_depth=0, group_index=0, link_count=1),
    ):
        raise ValueError("synthetic failure")

    # Assert
    [span] = span_recorder.spans_named(LINK_GROUP_SPAN)
    assert span.ended
    assert span.attributes[CHILD_GET_COUNT] == 0
    assert span.status.description == "ValueError"


@pytest.mark.parametrize("traversal", TRAVERSALS, ids=[traversal.name for traversal in TRAVERSALS])
async def test_child_get_count_counts_a_retried_request_one_time(
    traversal: Traversal, span_recorder: SpanRecorder
) -> None:
    # Arrange
    retried_child_get = f"Condition?patient={PATIENT_ID}"
    fhir_server = MockFhirServer(answers=ONE_GROUP.answers, failures={retried_child_get: 1})
    fhir_client = FhirClient().url(BASE_URL).retry_count(1)

    # Act
    with aioresponses() as mocked_fhir_server:
        fhir_server.install(mocked_fhir_server)
        await traversal.run(fhir_client, ONE_GROUP.graph, 1, False)

    # Assert
    # the retry is a second attempt of the same request: the mock server gets it, but the count does not
    assert fhir_server.requests.count(retried_child_get) == 2
    assert _link_groups(span_recorder.spans_named(LINK_GROUP_SPAN)) == ONE_GROUP.link_groups
