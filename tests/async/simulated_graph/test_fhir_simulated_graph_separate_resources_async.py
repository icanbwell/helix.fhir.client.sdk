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

from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


async def test_fhir_simulated_graph_async() -> None:
    print("")
    data_dir: Path = Path(__file__).parent.joinpath("./")
    graph_json: Dict[str, Any]
    with open(data_dir.joinpath("graphs").joinpath("aetna.json"), "r") as file:
        contents = file.read()
        graph_json = json.loads(contents)

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
        request=mock_request(path=f"/{relative_url}/Patient/1", method="GET"),
        response=mock_response(body=response_text),
        timing=times(1),
    )

    response_text = {"resourceType": "Practitioner", "id": "5"}
    mock_client.expect(
        request=mock_request(path=f"/{relative_url}/Practitioner/5", method="GET"),
        response=mock_response(body=response_text),
        timing=times(1),
    )

    response_text = {"resourceType": "Organization", "id": "6"}
    mock_client.expect(
        request=mock_request(path=f"/{relative_url}/Organization/6", method="GET"),
        response=mock_response(body=response_text),
        timing=times(1),
    )

    response_text = {
        "entry": [
            {
                "resource": {
                    "resourceType": "Coverage",
                    "id": "7",
                    "payor": [{"reference": "Organization/CoveragePayor"}],
                }
            }
        ]
    }
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Coverage",
            querystring={"patient": "1"},
            method="GET",
        ),
        response=mock_response(body=response_text),
        timing=times(1),
    )

    response_text = {"resourceType": "Organization", "id": "CoveragePayor"}
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Organization/CoveragePayor", method="GET"
        ),
        response=mock_response(body=response_text),
        timing=times(1),
    )

    response_text = {
        "entry": [{"resource": {"resourceType": "Observation", "id": "8"}}]
    }
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Observation",
            querystring={
                "patient": "1",
                "category": "vital-signs,social-history,laboratory",
            },
            method="GET",
        ),
        response=mock_response(body=response_text),
        timing=times(1),
    )

    fhir_client = FhirClient()

    fhir_client = fhir_client.log_level("DEBUG")

    fhir_client = fhir_client.url(absolute_url).resource("Patient")

    fhir_client.extra_context_to_return({"service_slug": "medstar"})

    auth_access_token = "my_access_token"
    if auth_access_token:
        fhir_client = fhir_client.set_access_token(auth_access_token)

    response: FhirGetResponse = await fhir_client.simulate_graph_async(
        id_="1",
        graph_json=graph_json,
        contained=False,
        separate_bundle_resources=True,
    )
    print(response.responses)

    expected_json = {
        "Patient": [
            {
                "resourceType": "Patient",
                "id": "1",
                "generalPractitioner": [{"reference": "Practitioner/5"}],
                "managingOrganization": {"reference": "Organization/6"},
            }
        ],
        "Practitioner": [{"resourceType": "Practitioner", "id": "5"}],
        "Organization": [
            {"resourceType": "Organization", "id": "6"},
            {"resourceType": "Organization", "id": "CoveragePayor"},
        ],
        "Coverage": [
            {
                "resourceType": "Coverage",
                "id": "7",
                "payor": [{"reference": "Organization/CoveragePayor"}],
            }
        ],
        "OperationOutcome": [
            {
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "error",
                        "code": "not-found",
                        "details": {
                            "coding": [
                                {
                                    "system": "https://www.icanbwell.com/url",
                                    "code": "http://mock-server:1080/test_fhir_simulated_graph_async/ExplanationOfBenefit?patient=1",
                                },
                                {
                                    "system": "https://www.icanbwell.com/resourceType",
                                    "code": "ExplanationOfBenefit",
                                },
                                {
                                    "system": "https://www.icanbwell.com/statuscode",
                                    "code": 404,
                                },
                                {
                                    "system": "https://www.icanbwell.com/accessToken",
                                    "code": "my_access_token",
                                },
                            ]
                        },
                        "diagnostics": '{"url": "http://mock-server:1080/test_fhir_simulated_graph_async/ExplanationOfBenefit?patient=1", "error": "NotFound", "status": 404, "extra_context_to_return": {"service_slug": "medstar"}, "accessToken": "my_access_token", "requestId": null, "resourceType": "ExplanationOfBenefit", "id": null}',
                    }
                ],
            },
            {
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "error",
                        "code": "not-found",
                        "details": {
                            "coding": [
                                {
                                    "system": "https://www.icanbwell.com/url",
                                    "code": "http://mock-server:1080/test_fhir_simulated_graph_async/MedicationRequest?patient=1",
                                },
                                {
                                    "system": "https://www.icanbwell.com/resourceType",
                                    "code": "MedicationRequest",
                                },
                                {
                                    "system": "https://www.icanbwell.com/statuscode",
                                    "code": 404,
                                },
                                {
                                    "system": "https://www.icanbwell.com/accessToken",
                                    "code": "my_access_token",
                                },
                            ]
                        },
                        "diagnostics": '{"url": "http://mock-server:1080/test_fhir_simulated_graph_async/MedicationRequest?patient=1", "error": "NotFound", "status": 404, "extra_context_to_return": {"service_slug": "medstar"}, "accessToken": "my_access_token", "requestId": null, "resourceType": "MedicationRequest", "id": null}',
                    }
                ],
            },
            {
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "error",
                        "code": "not-found",
                        "details": {
                            "coding": [
                                {
                                    "system": "https://www.icanbwell.com/url",
                                    "code": "http://mock-server:1080/test_fhir_simulated_graph_async/MedicationDispense?patient=1",
                                },
                                {
                                    "system": "https://www.icanbwell.com/resourceType",
                                    "code": "MedicationDispense",
                                },
                                {
                                    "system": "https://www.icanbwell.com/statuscode",
                                    "code": 404,
                                },
                                {
                                    "system": "https://www.icanbwell.com/accessToken",
                                    "code": "my_access_token",
                                },
                            ]
                        },
                        "diagnostics": '{"url": "http://mock-server:1080/test_fhir_simulated_graph_async/MedicationDispense?patient=1", "error": "NotFound", "status": 404, "extra_context_to_return": {"service_slug": "medstar"}, "accessToken": "my_access_token", "requestId": null, "resourceType": "MedicationDispense", "id": null}',
                    }
                ],
            },
        ],
        "Observation": [{"resourceType": "Observation", "id": "8"}],
    }

    assert json.loads(response.responses) == expected_json
