import json
from pathlib import Path

import requests_mock

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


def test_fhir_client_bundle_not_expanded() -> None:
    with requests_mock.Mocker() as mock:
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
            test_path.joinpath("./practitioner_graph_sample_not_expanded.json")
        ) as f:
            expected_response = json.load(f)
        mock.post(
            f"{url}/Patient/$graph?id=1710949219,1053306548&contained=true",
            json=response_text,
        )

        fhir_client = (
            FhirClient()
            .action("$graph")
            .id_(["1710949219", "1053306548"])
            .additional_parameters(["&contained=true"])
            .action_payload(action_payload)
            .expand_fhir_bundle(False)
        )
        fhir_client = fhir_client.url(url).resource("Patient")
        response: FhirGetResponse = fhir_client.get()

        assert response.responses == json.dumps(expected_response)
