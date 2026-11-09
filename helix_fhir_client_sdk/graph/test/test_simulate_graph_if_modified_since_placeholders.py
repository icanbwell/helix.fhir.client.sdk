import re
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from aioresponses import CallbackResult, aioresponses
from multidict import MultiDictProxy
from yarl import URL

from helix_fhir_client_sdk.graph.simulated_graph_processor_mixin import (
    SimulatedGraphProcessorMixin,
)
from helix_fhir_client_sdk.graph.test.test_simulate_graph_processor_mixin import (
    get_graph_processor,
)

# Encounter opts into the full-instant placeholder while Observation keeps the date-only one, so a
# single graph checks both renderings side by side.
GRAPH_JSON: dict[str, Any] = {
    "id": "1",
    "name": "Test Graph",
    "resourceType": "GraphDefinition",
    "start": "Patient",
    "link": [
        {"target": [{"type": "Encounter", "params": "patient={ref}&date=ge{ifModifiedSinceDateTime}"}]},
        {"target": [{"type": "Observation", "params": "patient={ref}&category=laboratory&date=ge{ifModifiedSince}"}]},
    ],
}


def mock_graph_responses(m: aioresponses, captured_queries: dict[str, MultiDictProxy[str]]) -> None:
    """
    Mocks the Patient read plus one search per target, recording each search's decoded query
    parameters (repeated keys kept) so the assertions see exactly what the FHIR server would
    receive, independent of how the value was percent-encoded on the wire.
    """
    m.get("http://example.com/fhir/Patient/1", payload={"resourceType": "Patient", "id": "1"})

    for resource_type in ("Encounter", "Observation"):

        async def capture_search(url: Any, *, _resource_type: str = resource_type, **kwargs: Any) -> CallbackResult:
            captured_queries[_resource_type] = URL(str(url)).query
            return CallbackResult(
                status=200,
                payload={
                    "resourceType": "Bundle",
                    "entry": [{"resource": {"resourceType": _resource_type, "id": "1"}}],
                },
            )

        m.get(re.compile(rf"http://example\.com/fhir/{resource_type}\?.*"), callback=capture_search)


async def run_graph(
    *, entry_point: str, graph_processor: SimulatedGraphProcessorMixin, if_modified_since: datetime | None
) -> None:
    if entry_point == "simulate_graph_async":
        await graph_processor.simulate_graph_async(
            id_="1", graph_json=GRAPH_JSON, contained=False, ifModifiedSince=if_modified_since
        )
    else:
        async for _ in graph_processor.simulate_graph_by_resource_type_async(
            id_="1", graph_json=GRAPH_JSON, contained=False, ifModifiedSince=if_modified_since
        ):
            pass


@pytest.mark.asyncio
@pytest.mark.parametrize("entry_point", ["simulate_graph_async", "simulate_graph_by_resource_type_async"])
@pytest.mark.parametrize(
    ("if_modified_since", "expected_encounter_dates", "expected_observation_dates"),
    [
        pytest.param(
            datetime(2023, 10, 1, 15, 30, tzinfo=UTC),
            ["ge2023-10-01T00:00:00Z"],
            ["ge2023-10-01"],
            id="utc",
        ),
        pytest.param(
            datetime(2023, 10, 1, 15, 30),
            ["ge2023-10-01T00:00:00Z"],
            ["ge2023-10-01"],
            id="naive-treated-as-utc",
        ),
        pytest.param(
            datetime(2023, 10, 1, 22, 0, tzinfo=timezone(timedelta(hours=-5))),
            ["ge2023-10-02T00:00:00Z"],
            ["ge2023-10-02"],
            id="offset-converted-to-next-utc-day",
        ),
        pytest.param(None, [], [], id="no-cutoff-drops-the-date-param"),
    ],
)
async def test_if_modified_since_placeholders_render_into_reverse_link_params(
    entry_point: str,
    if_modified_since: datetime | None,
    expected_encounter_dates: list[str],
    expected_observation_dates: list[str],
) -> None:
    """
    DCON-5571: {ifModifiedSince} renders just the UTC date, which Cerner rejects on Encounter's
    `date` search parameter with 400 "date: must have a time". {ifModifiedSinceDateTime} renders
    the same UTC day at midnight as a full instant for targets that opt into it, leaves
    {ifModifiedSince} targets unchanged, and is dropped like {ifModifiedSince} when there is no
    cutoff (a first pull).
    """
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor()
    captured_queries: dict[str, MultiDictProxy[str]] = {}

    with aioresponses() as m:
        mock_graph_responses(m, captured_queries)

        await run_graph(entry_point=entry_point, graph_processor=graph_processor, if_modified_since=if_modified_since)

    assert captured_queries["Encounter"].getall("patient") == ["1"]
    assert captured_queries["Encounter"].getall("date", []) == expected_encounter_dates
    assert captured_queries["Observation"].getall("category") == ["laboratory"]
    assert captured_queries["Observation"].getall("date", []) == expected_observation_dates
