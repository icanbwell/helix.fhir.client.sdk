from logging import Logger
from os import environ

from compressedfhir.fhir.fhir_resource_list import FhirResourceList
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
from tests.logger_for_test import LoggerForTest


async def test_fhir_graph_multiple_ids_in_batches_async() -> None:
    logger: Logger = LoggerForTest()
    test_name = "test_fhir_graph_multiple_ids_in_batches_async"

    environ["LOG_LEVEL"] = "DEBUG"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(base_url=mock_server_url)

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    graph_definition = GraphDefinition(
        id_="123",
        name="my_everything",
        start="Patient",
        link=[
            GraphDefinitionLink(target=[GraphDefinitionTarget(type_="Location", params="managingOrganization={ref}")]),
            GraphDefinitionLink(
                target=[
                    GraphDefinitionTarget(
                        type_="HealthcareService",
                        params="providedBy={ref}",
                        link=[
                            GraphDefinitionLink(target=[GraphDefinitionTarget(type_="Schedule", params="actor={ref}")])
                        ],
                    )
                ]
            ),
        ],
    )

    response_text1 = {
        "resourceType": "Bundle",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "1"}},
        ],
    }
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Patient/1/$graph",
            method="POST",
        ),
        response=mock_response(body=response_text1),
        timing=times(1),
        file_path=None,
    )

    response_text2 = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "2",
                    "contained": [{"resourceType": "Location", "id": "1"}],
                }
            },
        ],
    }
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Patient/2/$graph",
            method="POST",
        ),
        response=mock_response(body=response_text2),
        timing=times(1),
        file_path=None,
    )

    fhir_client = FhirClient()

    fhir_client = fhir_client.url(absolute_url).resource("Patient")
    fhir_client = fhir_client.page_size(1)  # process one by one
    responses: list[FhirGetResponse] = []
    async for response in fhir_client.graph_async(
        id_=["1", "2"],
        graph_definition=graph_definition,
        contained=True,
    ):
        logger.info(f"Response Chunk: {response.get_response_text()}")
        responses.append(response)

    assert len(responses) == 2
    logger.info(f"Response: {responses[0].get_response_text()}")
    assert responses[0].get_response_text()
    resources = responses[0].get_resources()
    assert isinstance(resources, FhirResourceList)
    assert [r.dict() for r in resources] == [{"id": "1", "resourceType": "Patient"}]
    resources = responses[1].get_resources()
    assert isinstance(resources, FhirResourceList)
    assert [r.dict() for r in resources] == [
        {
            "contained": [{"id": "1", "resourceType": "Location"}],
            "id": "2",
            "resourceType": "Patient",
        }
    ]
