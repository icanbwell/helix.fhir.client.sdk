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


async def test_fhir_simulated_graph_with_errors_async() -> None:
    print("")
    data_dir: Path = Path(__file__).parent.joinpath("./")
    graph_json: Dict[str, Any]
    with open(data_dir.joinpath("graphs").joinpath("aetna.json"), "r") as file:
        contents = file.read()
        graph_json = json.loads(contents)

    test_name = "test_fhir_simulated_graph_with_errors_async"

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

    response_text = {"entry": [{"resource": {"resourceType": "Coverage", "id": "7"}}]}
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Coverage",
            querystring={"patient": "1"},
            method="GET",
        ),
        response=mock_response(body=response_text),
        timing=times(1),
    )

    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Observation",
            querystring={
                "patient": "1",
                "category": "vital-signs,social-history,laboratory",
            },
            method="GET",
        ),
        response=mock_response(code=401),
        timing=times(1),
    )

    fhir_client = FhirClient()
    fhir_client = fhir_client.expand_fhir_bundle(False)
    fhir_client = fhir_client.url(absolute_url).resource("Patient")
    fhir_client = fhir_client.extra_context_to_return({"slug": "1234"})
    response: FhirGetResponse = await fhir_client.simulate_graph_async(
        id_="1",
        graph_json=graph_json,
        contained=False,
        separate_bundle_resources=False,
    )
    print(response.responses)

    assert response.url == f"http://mock-server:1080/{test_name}"
    assert response.extra_context_to_return == {"slug": "1234"}

    expected_json = {
        "entry": [
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_with_errors_async/Patient/1",
                },
                "resource": {
                    "generalPractitioner": [{"reference": "Practitioner/5"}],
                    "id": "1",
                    "managingOrganization": {"reference": "Organization/6"},
                    "resourceType": "Patient",
                },
                "response": {"status": "200"},
            },
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_with_errors_async/Practitioner/5",
                },
                "resource": {"id": "5", "resourceType": "Practitioner"},
                "response": {"status": "200"},
            },
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_with_errors_async/Organization/6",
                },
                "resource": {"id": "6", "resourceType": "Organization"},
                "response": {"status": "200"},
            },
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_with_errors_async/Coverage?patient=1",
                },
                "resource": {"id": "7", "resourceType": "Coverage"},
                "response": {"status": "200"},
            },
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_with_errors_async/ExplanationOfBenefit?patient=1",
                },
                "resource": {
                    "issue": [
                        {
                            "code": "not-found",
                            "details": {
                                "coding": [
                                    {
                                        "code": "http://mock-server:1080/test_fhir_simulated_graph_with_errors_async/ExplanationOfBenefit?patient=1",
                                        "system": "https://www.icanbwell.com/url",
                                    },
                                    {
                                        "code": "ExplanationOfBenefit",
                                        "system": "https://www.icanbwell.com/resourceType",
                                    },
                                    {
                                        "code": 404,
                                        "system": "https://www.icanbwell.com/statuscode",
                                    },
                                ]
                            },
                            "diagnostics": '{"url": '
                            '"http://mock-server:1080/test_fhir_simulated_graph_with_errors_async/ExplanationOfBenefit?patient=1", '
                            '"error": "NotFound", '
                            '"status": 404, '
                            '"extra_context_to_return": '
                            '{"slug": "1234"}, '
                            '"accessToken": null, '
                            '"requestId": null, '
                            '"resourceType": '
                            '"ExplanationOfBenefit", '
                            '"id": null}',
                            "severity": "error",
                        }
                    ],
                    "resourceType": "OperationOutcome",
                },
                "response": {"status": "404"},
            },
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_with_errors_async/Observation?patient=1&category=vital-signs,social-history,laboratory",
                },
                "resource": {
                    "issue": [
                        {
                            "code": "expired",
                            "details": {
                                "coding": [
                                    {
                                        "code": "http://mock-server:1080/test_fhir_simulated_graph_with_errors_async/Observation?patient=1&category=vital-signs,social-history,laboratory",
                                        "system": "https://www.icanbwell.com/url",
                                    },
                                    {
                                        "code": "Observation",
                                        "system": "https://www.icanbwell.com/resourceType",
                                    },
                                    {
                                        "code": 401,
                                        "system": "https://www.icanbwell.com/statuscode",
                                    },
                                ]
                            },
                            "diagnostics": '{"url": '
                            '"http://mock-server:1080/test_fhir_simulated_graph_with_errors_async/Observation?patient=1&category=vital-signs,social-history,laboratory", '
                            '"error": "UnAuthorized", '
                            '"status": 401, '
                            '"extra_context_to_return": '
                            '{"slug": "1234"}, '
                            '"accessToken": null, '
                            '"requestId": null, '
                            '"resourceType": '
                            '"Observation", "id": null}',
                            "severity": "error",
                        }
                    ],
                    "resourceType": "OperationOutcome",
                },
                "response": {"status": "401"},
            },
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_with_errors_async/MedicationRequest?patient=1",
                },
                "resource": {
                    "issue": [
                        {
                            "code": "not-found",
                            "details": {
                                "coding": [
                                    {
                                        "code": "http://mock-server:1080/test_fhir_simulated_graph_with_errors_async/MedicationRequest?patient=1",
                                        "system": "https://www.icanbwell.com/url",
                                    },
                                    {
                                        "code": "MedicationRequest",
                                        "system": "https://www.icanbwell.com/resourceType",
                                    },
                                    {
                                        "code": 404,
                                        "system": "https://www.icanbwell.com/statuscode",
                                    },
                                ]
                            },
                            "diagnostics": '{"url": '
                            '"http://mock-server:1080/test_fhir_simulated_graph_with_errors_async/MedicationRequest?patient=1", '
                            '"error": "NotFound", '
                            '"status": 404, '
                            '"extra_context_to_return": '
                            '{"slug": "1234"}, '
                            '"accessToken": null, '
                            '"requestId": null, '
                            '"resourceType": '
                            '"MedicationRequest", "id": '
                            "null}",
                            "severity": "error",
                        }
                    ],
                    "resourceType": "OperationOutcome",
                },
                "response": {"status": "404"},
            },
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_with_errors_async/MedicationDispense?patient=1",
                },
                "resource": {
                    "issue": [
                        {
                            "code": "not-found",
                            "details": {
                                "coding": [
                                    {
                                        "code": "http://mock-server:1080/test_fhir_simulated_graph_with_errors_async/MedicationDispense?patient=1",
                                        "system": "https://www.icanbwell.com/url",
                                    },
                                    {
                                        "code": "MedicationDispense",
                                        "system": "https://www.icanbwell.com/resourceType",
                                    },
                                    {
                                        "code": 404,
                                        "system": "https://www.icanbwell.com/statuscode",
                                    },
                                ]
                            },
                            "diagnostics": '{"url": '
                            '"http://mock-server:1080/test_fhir_simulated_graph_with_errors_async/MedicationDispense?patient=1", '
                            '"error": "NotFound", '
                            '"status": 404, '
                            '"extra_context_to_return": '
                            '{"slug": "1234"}, '
                            '"accessToken": null, '
                            '"requestId": null, '
                            '"resourceType": '
                            '"MedicationDispense", '
                            '"id": null}',
                            "severity": "error",
                        }
                    ],
                    "resourceType": "OperationOutcome",
                },
                "response": {"status": "404"},
            },
        ]
    }

    assert json.loads(response.responses) == expected_json
