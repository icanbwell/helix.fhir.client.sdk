import json

from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.graph.graph_definition import (
    GraphDefinition,
    GraphDefinitionLink,
    GraphDefinitionTarget,
)
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


async def test_fhir_graph_async() -> None:
    test_name = "test_fhir_graph_async"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(
        base_url=mock_server_url
    )

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    response_text = {"resourceType": "Patient", "id": "12355"}

    graph_definition = GraphDefinition(
        id_="123",
        name="my_everything",
        start="Patient",
        link=[
            GraphDefinitionLink(
                target=[
                    GraphDefinitionTarget(
                        type_="Location", params="managingOrganization={ref}"
                    )
                ]
            ),
            GraphDefinitionLink(
                target=[
                    GraphDefinitionTarget(
                        type_="HealthcareService",
                        params="providedBy={ref}",
                        link=[
                            GraphDefinitionLink(
                                target=[
                                    GraphDefinitionTarget(
                                        type_="Schedule", params="actor={ref}"
                                    )
                                ]
                            )
                        ],
                    )
                ]
            ),
        ],
    )

    mock_client.expect(
        mock_request(path=f"/{relative_url}/Patient/1/$graph", method="POST"),
        mock_response(body=response_text),
        timing=times(1),
    )

    fhir_client = FhirClient()

    fhir_client = fhir_client.url(absolute_url).resource("Patient")
    response: FhirGetResponse = await fhir_client.graph_async(
        graph_definition=graph_definition, contained=False
    )
    assert json.loads(response.responses) == response_text
