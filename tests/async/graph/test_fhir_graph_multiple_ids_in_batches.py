from os import environ
from typing import List

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


async def test_fhir_graph_multiple_ids_in_batches_async() -> None:
    print("")
    test_name = "test_fhir_graph_multiple_ids_in_batches_async"

    environ["LOG_LEVEL"] = "DEBUG"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(
        base_url=mock_server_url
    )

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

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
        request=mock_request(
            path=f"/{relative_url}/Patient/1/$graph",
            method="POST",
        ),
        response=mock_response(body={"resourceType": "Patient", "id": "1"}),
        timing=times(1),
        file_path=None,
    )

    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Patient/2/$graph",
            method="POST",
        ),
        response=mock_response(body={"resourceType": "Patient", "id": "2"}),
        timing=times(1),
        file_path=None,
    )

    fhir_client = FhirClient()

    fhir_client = fhir_client.url(absolute_url).resource("Patient")
    fhir_client = fhir_client.page_size(1)  # process one by one
    responses: List[FhirGetResponse] = []
    async for response in fhir_client.graph_async(
        id_=["1", "2"],
        graph_definition=graph_definition,
        contained=False,
        process_in_pages=False,
    ):
        print(f"Response Chunk: {response.responses}")
        responses.append(response)

    assert len(responses) == 2
    print(f"Response: {responses[0].responses}")
    assert responses[0].responses
    assert responses[0].get_resources() == [{"id": "1", "resourceType": "Patient"}]
    assert responses[1].get_resources() == [{"id": "2", "resourceType": "Patient"}]
