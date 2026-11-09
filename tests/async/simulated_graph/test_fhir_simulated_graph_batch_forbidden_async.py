from dataclasses import dataclass
from typing import Any

import pytest
from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.graph.resource_type_completion_event import ResourceTypeCompletionEvent
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.utilities.cache.request_cache import RequestCache

MOCK_SERVER_URL = "http://mock-server:1080"

GRAPH: dict[str, Any] = {
    "resourceType": "GraphDefinition",
    "id": "o",
    "name": "batch_forbidden",
    "status": "active",
    "start": "Patient",
    "link": [{"path": "generalPractitioner[x]", "target": [{"type": "Practitioner"}]}],
}

FORBIDDEN_BODY: dict[str, Any] = {
    "resourceType": "OperationOutcome",
    "issue": [{"severity": "fatal", "code": "forbidden", "details": {"text": "not authorized"}}],
}
NOT_FOUND_BODY: dict[str, Any] = {
    "resourceType": "OperationOutcome",
    "issue": [{"severity": "error", "code": "not-found"}],
}


@dataclass(frozen=True)
class BatchCase:
    name: str
    practitioner_ids: tuple[str, ...]
    batch_status: int | None
    """Status of Practitioner?_id=... ; None when the ids are few enough that no batch is sent."""
    status_by_id: dict[str, int]
    """What the server returns for Practitioner/<id> if it is asked."""
    expected_ids: list[str]
    expected_outcome: str | None
    """Link outcome on the completion event; None where this change leaves it as it was."""
    expected_error_type: str | None
    expected_cache_status: dict[str, int] | None
    """Cached status per id; None where this change leaves it as it was."""
    expected_reads: tuple[str, ...]
    """Ids fetched as Practitioner/<id>."""


CASES = [
    BatchCase(
        name="forbidden_batch_and_probe_skips_the_rest",
        practitioner_ids=("1", "2", "3"),
        batch_status=403,
        status_by_id={"1": 403, "2": 403, "3": 403},
        expected_ids=[],
        expected_outcome="error",
        expected_error_type="HttpStatus403",
        expected_cache_status={"1": 403, "2": 403, "3": 403},
        expected_reads=("1",),
    ),
    BatchCase(
        # The probe only reads the first id. If it is forbidden, the rest are not read even when
        # the server would have returned them: an accepted trade-off, since in production every id
        # behind a forbidden batch has also been forbidden on its own.
        name="forbidden_probe_does_not_read_other_ids",
        practitioner_ids=("1", "2", "3"),
        batch_status=403,
        status_by_id={"1": 403, "2": 200, "3": 200},
        expected_ids=[],
        expected_outcome="error",
        expected_error_type="HttpStatus403",
        expected_cache_status={"1": 403, "2": 403, "3": 403},
        expected_reads=("1",),
    ),
    BatchCase(
        name="readable_probe_falls_back_to_one_by_one",
        practitioner_ids=("1", "2", "3"),
        batch_status=403,
        status_by_id={"1": 200, "2": 403, "3": 200},
        expected_ids=["1", "3"],
        expected_outcome="success",
        expected_error_type=None,
        expected_cache_status=None,
        expected_reads=("1", "2", "3"),
    ),
    BatchCase(
        name="probe_not_found_falls_back_to_one_by_one",
        practitioner_ids=("1", "2", "3"),
        batch_status=403,
        status_by_id={"1": 404, "2": 200, "3": 200},
        expected_ids=["2", "3"],
        expected_outcome=None,
        expected_error_type=None,
        expected_cache_status=None,
        expected_reads=("1", "2", "3"),
    ),
    BatchCase(
        name="unsupported_batch_still_falls_back_to_one_by_one",
        practitioner_ids=("1", "2", "3"),
        batch_status=400,
        status_by_id={"1": 200, "2": 200, "3": 200},
        expected_ids=["1", "2", "3"],
        expected_outcome="success",
        expected_error_type=None,
        expected_cache_status={"1": 200, "2": 200, "3": 200},
        expected_reads=("1", "2", "3"),
    ),
    BatchCase(
        name="single_id_forbidden_is_reported",
        practitioner_ids=("1",),
        batch_status=None,
        status_by_id={"1": 403},
        expected_ids=[],
        expected_outcome="error",
        expected_error_type="HttpStatus403",
        expected_cache_status=None,
        expected_reads=("1",),
    ),
]


def _expect_requests(mock_client: MockServerFriendlyClient, relative_url: str, case: BatchCase) -> None:
    mock_client.expect(
        request=mock_request(path=f"/{relative_url}/Patient/1", method="GET"),
        response=mock_response(
            body={
                "resourceType": "Patient",
                "id": "1",
                "generalPractitioner": [{"reference": f"Practitioner/{i}"} for i in case.practitioner_ids],
            }
        ),
        timing=times(1),
    )
    if case.batch_status is not None:
        mock_client.expect(
            request=mock_request(
                path=f"/{relative_url}/Practitioner",
                querystring={"_id": ",".join(case.practitioner_ids)},
                method="GET",
            ),
            response=mock_response(code=case.batch_status, body=FORBIDDEN_BODY),
            timing=times(1),
        )
    for practitioner_id, status in case.status_by_id.items():
        body = {
            200: {"resourceType": "Practitioner", "id": practitioner_id},
            403: FORBIDDEN_BODY,
            404: NOT_FOUND_BODY,
        }[status]
        mock_client.expect(
            request=mock_request(path=f"/{relative_url}/Practitioner/{practitioner_id}", method="GET"),
            response=mock_response(code=status, body=body),
            timing=times(1),
        )


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
async def test_fhir_simulated_graph_batch_forbidden_async(case: BatchCase) -> None:
    # Arrange
    relative_url = f"test_fhir_simulated_graph_batch_forbidden_async_{case.name}"
    mock_client = MockServerFriendlyClient(base_url=MOCK_SERVER_URL)
    mock_client.clear(f"/{relative_url}/*.*")
    mock_client.reset()
    _expect_requests(mock_client, relative_url, case)

    completion_events: list[ResourceTypeCompletionEvent] = []

    async def on_resource_type_completed(event: ResourceTypeCompletionEvent) -> None:
        completion_events.append(event)

    cache = RequestCache(clear_cache_at_the_end=False)
    fhir_client = (
        FhirClient()
        .expand_fhir_bundle(False)
        .url(f"{MOCK_SERVER_URL}/{relative_url}")
        .resource("Patient")
        .set_create_operation_outcome_for_error(True)
    )

    # Act
    response: FhirGetResponse | None = await FhirGetResponse.from_async_generator(
        fhir_client.simulate_graph_streaming_async(
            id_="1",
            graph_json=GRAPH,
            contained=False,
            request_size=10,
            input_cache=cache,
            on_resource_type_completed=on_resource_type_completed,
        )
    )

    # Assert
    assert response is not None
    returned_practitioner_ids = sorted(
        r["id"] for r in response.get_resources() if r.get("resourceType") == "Practitioner"
    )
    assert returned_practitioner_ids == case.expected_ids

    practitioner_events = [e for e in completion_events if e.resource_types == ["Practitioner"]]
    assert len(practitioner_events) == 1
    if case.expected_outcome is not None:
        assert practitioner_events[0].outcome == case.expected_outcome
        assert practitioner_events[0].error_type == case.expected_error_type

    if case.expected_cache_status is not None:
        cached_status = {}
        for practitioner_id in case.practitioner_ids:
            entry = await cache.get_async(resource_type="Practitioner", resource_id=practitioner_id)
            assert entry is not None
            cached_status[practitioner_id] = entry.status
        assert cached_status == case.expected_cache_status

    read_prefix = f"/{relative_url}/Practitioner/"
    reads = sorted(
        r.path.removeprefix(read_prefix)
        for r in mock_client.retrieve_requests()
        if r.path and r.path.startswith(read_prefix)
    )
    assert reads == list(case.expected_reads)
