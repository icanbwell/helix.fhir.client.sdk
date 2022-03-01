import json
from pathlib import Path

from mockserver_client.mockserver_client import (
    mock_request,
    MockServerFriendlyClient,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


async def test_fhir_client_bundle_separated_async() -> None:
    test_name = "test_fhir_client_bundle_separated_async"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(
        base_url=mock_server_url
    )

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    test_path = Path(__file__).parent
    with open(test_path.joinpath("../practitioner_graph_sample.json")) as f:
        response_text = json.load(f)

    action_payload = {
        "resourceType": "GraphDefinition",
        "id": "o",
        "name": "provider_everything",
        "status": "active",
        "start": "Practitioner",
        "link": [
            {
                "description": "Practitioner Roles for this Practitioner",
                "target": [
                    {
                        "type": "PractitionerRole",
                        "params": "practitioner={ref}",
                        "link": [
                            {
                                "path": "organization",
                                "target": [{"type": "Organization"}],
                            },
                            {
                                "path": "location[x]",
                                "target": [{"type": "Location"}],
                            },
                            {
                                "path": "healthcareService[x]",
                                "target": [{"type": "HealthcareService"}],
                            },
                        ],
                    }
                ],
            }
        ],
    }

    mock_client.expect(
        mock_request(
            path=f"/{relative_url}/Patient/$graph",
            method="POST",
            querystring={"id": "1710949219,1053306548", "contained": "true"},
        ),
        mock_response(body=response_text),
        timing=times(1),
    )

    fhir_client = (
        FhirClient()
        .action("$graph")
        .id_(["1710949219", "1053306548"])
        .additional_parameters(["&contained=true"])
        .action_payload(action_payload)
        .separate_bundle_resources(True)
    )

    fhir_client = fhir_client.url(absolute_url).resource("Patient")
    response: FhirGetResponse = await fhir_client.get_async()

    with open(test_path.joinpath("./practitioner_graph_sample_separated.json")) as f:
        expected_response = json.load(f)

    assert json.loads(response.responses) == expected_response
