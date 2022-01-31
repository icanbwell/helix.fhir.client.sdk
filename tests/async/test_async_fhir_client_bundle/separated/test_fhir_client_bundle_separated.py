import json
from pathlib import Path

from aioresponses import aioresponses

from helix_fhir_client_sdk.async_fhir_client import AsyncFhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


async def test_async_fhir_client_bundle_separated() -> None:
    mock: aioresponses
    with aioresponses() as mock:  # type: ignore
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
        url = "http://foo"
        test_path = Path(__file__).parent
        with open(test_path.joinpath("../practitioner_graph_sample.json")) as f:
            response_text = json.load(f)
        with open(
            test_path.joinpath("./practitioner_graph_sample_separated.json")
        ) as f:
            expected_response = json.load(f)
        mock.post(
            f"{url}/Patient/$graph?id=1710949219,1053306548&contained=true",
            payload=response_text,
        )

        fhir_client = (
            AsyncFhirClient()
            .action("$graph")
            .id_(["1710949219", "1053306548"])
            .additional_parameters(["&contained=true"])
            .action_payload(action_payload)
            .separate_bundle_resources(True)
        )
        fhir_client = fhir_client.url(url).resource("Patient")
        response: FhirGetResponse = await fhir_client.get()

        assert response.responses == json.dumps(expected_response)
