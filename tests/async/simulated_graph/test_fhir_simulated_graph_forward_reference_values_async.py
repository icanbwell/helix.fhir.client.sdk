from typing import Any

import pytest
from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse

MOCK_SERVER_URL = "http://mock-server:1080"

GRAPH: dict[str, Any] = {
    "resourceType": "GraphDefinition",
    "id": "o",
    "name": "forward_reference_values",
    "status": "active",
    "start": "Patient",
    "link": [{"path": "generalPractitioner[x]", "target": [{"type": "Practitioner"}]}],
}


@pytest.mark.parametrize(
    "general_practitioner,expected_batch_ids",
    [
        ([{"reference": "Practitioner/1"}, {"reference": "Practitioner/2"}], "1,2"),
        (
            [None, {}, {"reference": ""}, {"reference": "Practitioner/1"}, {"reference": "Practitioner/2"}],
            "1,2",
        ),
        (
            [{"reference": "Practitioner/2"}, {"display": "no reference"}, {"reference": "Practitioner/1"}],
            "1,2",
        ),
    ],
    ids=["plain-references", "null-and-empty-entries", "entry-without-reference"],
)
async def test_fhir_simulated_graph_forward_reference_values_async(
    general_practitioner: list[Any], expected_batch_ids: str
) -> None:
    # Arrange
    relative_url = "test_fhir_simulated_graph_forward_reference_values_async"
    mock_client = MockServerFriendlyClient(base_url=MOCK_SERVER_URL)
    mock_client.clear(f"/{relative_url}/*.*")
    mock_client.reset()
    mock_client.expect(
        request=mock_request(path=f"/{relative_url}/Patient/1", method="GET"),
        response=mock_response(
            body={"resourceType": "Patient", "id": "1", "generalPractitioner": general_practitioner}
        ),
        timing=times(1),
    )
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Practitioner",
            querystring={"_id": expected_batch_ids},
            method="GET",
        ),
        response=mock_response(
            body={
                "resourceType": "Bundle",
                "type": "searchset",
                "entry": [
                    {"resource": {"resourceType": "Practitioner", "id": "1"}},
                    {"resource": {"resourceType": "Practitioner", "id": "2"}},
                ],
            }
        ),
        timing=times(1),
    )
    fhir_client = FhirClient().expand_fhir_bundle(False).url(f"{MOCK_SERVER_URL}/{relative_url}").resource("Patient")

    # Act
    response: FhirGetResponse | None = await FhirGetResponse.from_async_generator(
        fhir_client.simulate_graph_streaming_async(
            id_="1",
            graph_json=GRAPH,
            contained=False,
            request_size=10,
        )
    )

    # Assert
    assert response is not None
    practitioner_ids = sorted(r["id"] for r in response.get_resources() if r.get("resourceType") == "Practitioner")
    assert practitioner_ids == ["1", "2"]
    batch_requests = [
        r for r in mock_client.retrieve_requests() if r.path and r.path == f"/{relative_url}/Practitioner"
    ]
    assert len(batch_requests) == 1
