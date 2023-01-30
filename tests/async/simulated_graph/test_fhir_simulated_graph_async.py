import json
from pathlib import Path
from typing import Dict, Any

from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.graph.graph_definition import (
    GraphDefinition,
)
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


async def test_fhir_simulated_graph_async() -> None:
    data_dir: Path = Path(__file__).parent.joinpath("./")
    graph_json: Dict[str, Any]
    with open(data_dir.joinpath("graphs").joinpath("aetna.json"), "r") as file:
        contents = file.read()
        graph_json = json.loads(contents)

    graph_definition: GraphDefinition = GraphDefinition.from_dict(graph_json)

    test_name = "test_fhir_simulated_graph_async"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(
        base_url=mock_server_url
    )

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    response_text = {
        "resourceType": "Patient",
        "id": "1",
        "generalPractitioner": [{"reference": "Practitioner/5"}],
        "managingOrganization": {"reference": "Organization/6"},
    }

    mock_client.expect(
        mock_request(path=f"/{relative_url}/Patient/1", method="GET"),
        mock_response(body=response_text),
        timing=times(1),
    )

    response_text = {"resourceType": "Practitioner", "id": "5"}
    mock_client.expect(
        mock_request(path=f"/{relative_url}/Practitioner/5", method="GET"),
        mock_response(body=response_text),
        timing=times(1),
    )

    response_text = {"resourceType": "Organization", "id": "6"}
    mock_client.expect(
        mock_request(path=f"/{relative_url}/Organization/6", method="GET"),
        mock_response(body=response_text),
        timing=times(1),
    )

    response_text = {"entry": [{"resourceType": "Coverage", "id": "7"}]}
    mock_client.expect(
        mock_request(
            path=f"/{relative_url}/Coverage",
            querystring={"patient": "1"},
            method="GET",
        ),
        mock_response(body=response_text),
        timing=times(1),
    )

    fhir_client = FhirClient()

    fhir_client = fhir_client.url(absolute_url).resource("Patient")
    response: FhirGetResponse = await fhir_client.simulate_graph_async(
        id_="1", graph_definition=graph_definition, contained=False
    )
    print(response.responses)
    # assert json.loads(response.responses) == response_text
