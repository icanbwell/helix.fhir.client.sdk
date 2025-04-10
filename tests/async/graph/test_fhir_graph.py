import json
from os import environ
from typing import List

import pytest
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


@pytest.mark.parametrize("use_data_streaming", [False])
async def test_fhir_graph_async(use_data_streaming: bool) -> None:
    print("")
    test_name = "test_fhir_graph_async"

    environ["LOG_LEVEL"] = "DEBUG"

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
        request=mock_request(path=f"/{relative_url}/Patient/1/$graph", method="POST"),
        response=mock_response(body=response_text),
        timing=times(1),
        file_path=None,
    )

    fhir_client = FhirClient()

    fhir_client = fhir_client.url(absolute_url).resource("Patient").id_("1")
    fhir_client = fhir_client.use_data_streaming(use_data_streaming)
    responses: List[FhirGetResponse] = []
    async for response in fhir_client.graph_async(
        id_="1", graph_definition=graph_definition, contained=False
    ):
        print(f"Response Chunk: {response.get_response_text()}")
        responses.append(response)

    assert len(responses) == 1
    print(f"Response: {responses[0].get_response_text()}")
    assert json.loads(responses[0].get_response_text()) == response_text
