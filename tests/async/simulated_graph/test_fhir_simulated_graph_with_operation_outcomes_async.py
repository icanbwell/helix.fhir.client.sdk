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


async def test_fhir_simulated_graph_with_operation_outcomes_async() -> None:
    print("")
    data_dir: Path = Path(__file__).parent.joinpath("./")
    graph_json: Dict[str, Any]
    with open(data_dir.joinpath("graphs").joinpath("aetna.json"), "r") as file:
        contents = file.read()
        graph_json = json.loads(contents)

    test_name = "test_fhir_simulated_graph_with_operation_outcomes_async"

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

    response_text = {
        "entry": [
            {"resource": {"resourceType": "Observation", "id": "8"}},
            {
                "resource": {
                    "resourceType": "OperationOutcome",
                    "issue": [
                        {
                            "severity": "warning",
                            "code": "suppressed",
                            "details": {
                                "coding": [
                                    {
                                        "system": "urn:oid:1.2.840.114350.1.13.0.1.7.2.657369",
                                        "code": "59204",
                                        "display": "The authenticated client's search request applies to a sub-resource that the client is not authorized for. Results of this sub-type will not be returned.",
                                    }
                                ],
                                "text": "The authenticated client's search request applies to a sub-resource that the client is not authorized for. Results of this sub-type will not be returned.",
                            },
                            "diagnostics": "Client not authorized for DocumentReference - Document Information. Search results of this type have not been included.",
                        }
                    ],
                }
            },
        ]
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
    fhir_client = fhir_client.expand_fhir_bundle(False)

    fhir_client.extra_context_to_return({"service_slug": "medstar"})

    auth_access_token = "my_access_token"
    if auth_access_token:
        fhir_client = fhir_client.set_access_token(auth_access_token)

    fhir_client = fhir_client.url(absolute_url).resource("Patient")
    response: FhirGetResponse = await fhir_client.simulate_graph_async(
        id_="1",
        graph_json=graph_json,
        contained=False,
        separate_bundle_resources=False,
    )
    print(response.responses)

    expected_json = {
        "entry": [
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_with_operation_outcomes_async/Patient/1",
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
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_with_operation_outcomes_async/Practitioner/5",
                },
                "resource": {"id": "5", "resourceType": "Practitioner"},
                "response": {"status": "200"},
            },
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_with_operation_outcomes_async/Organization/6",
                },
                "resource": {"id": "6", "resourceType": "Organization"},
                "response": {"status": "200"},
            },
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_with_operation_outcomes_async/Coverage?patient=1",
                },
                "resource": {"id": "7", "resourceType": "Coverage"},
                "response": {"status": "200"},
            },
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_with_operation_outcomes_async/Observation?patient=1&category=vital-signs,social-history,laboratory",
                },
                "resource": {"id": "8", "resourceType": "Observation"},
                "response": {"status": "200"},
            },
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_with_operation_outcomes_async/ExplanationOfBenefit?patient=1",
                },
                "resource": {
                    "issue": [
                        {
                            "code": "not-found",
                            "details": {
                                "coding": [
                                    {
                                        "code": "http://mock-server:1080/test_fhir_simulated_graph_with_operation_outcomes_async/ExplanationOfBenefit?patient=1",
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
                                    {
                                        "code": "my_access_token",
                                        "system": "https://www.icanbwell.com/accessToken",
                                    },
                                ]
                            },
                            "diagnostics": '{"url": '
                            '"http://mock-server:1080/test_fhir_simulated_graph_with_operation_outcomes_async/ExplanationOfBenefit?patient=1", '
                            '"error": "NotFound", '
                            '"status": 404, '
                            '"extra_context_to_return": '
                            '{"service_slug": '
                            '"medstar"}, "accessToken": '
                            '"my_access_token", '
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
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_with_operation_outcomes_async/Observation?patient=1&category=vital-signs,social-history,laboratory",
                },
                "resource": {
                    "issue": [
                        {
                            "code": "suppressed",
                            "details": {
                                "coding": [
                                    {
                                        "code": "59204",
                                        "display": "The "
                                        "authenticated "
                                        "client's "
                                        "search "
                                        "request "
                                        "applies "
                                        "to a "
                                        "sub-resource "
                                        "that "
                                        "the "
                                        "client "
                                        "is not "
                                        "authorized "
                                        "for. "
                                        "Results "
                                        "of "
                                        "this "
                                        "sub-type "
                                        "will "
                                        "not be "
                                        "returned.",
                                        "system": "urn:oid:1.2.840.114350.1.13.0.1.7.2.657369",
                                    },
                                    {
                                        "code": "http://mock-server:1080/test_fhir_simulated_graph_with_operation_outcomes_async/Observation?patient=1&category=vital-signs,social-history,laboratory",
                                        "system": "https://www.icanbwell.com/url",
                                    },
                                    {
                                        "code": "Observation",
                                        "system": "https://www.icanbwell.com/resourceType",
                                    },
                                    {
                                        "code": 200,
                                        "system": "https://www.icanbwell.com/statuscode",
                                    },
                                    {
                                        "code": "my_access_token",
                                        "system": "https://www.icanbwell.com/accessToken",
                                    },
                                ],
                                "text": "The authenticated "
                                "client's search "
                                "request applies to a "
                                "sub-resource that the "
                                "client is not "
                                "authorized for. "
                                "Results of this "
                                "sub-type will not be "
                                "returned.",
                            },
                            "diagnostics": "Client not authorized for "
                            "DocumentReference - "
                            "Document Information. "
                            "Search results of this "
                            "type have not been "
                            "included.",
                            "severity": "warning",
                        }
                    ],
                    "resourceType": "OperationOutcome",
                },
                "response": {"status": "200"},
            },
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_with_operation_outcomes_async/MedicationRequest?patient=1",
                },
                "resource": {
                    "issue": [
                        {
                            "code": "not-found",
                            "details": {
                                "coding": [
                                    {
                                        "code": "http://mock-server:1080/test_fhir_simulated_graph_with_operation_outcomes_async/MedicationRequest?patient=1",
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
                                    {
                                        "code": "my_access_token",
                                        "system": "https://www.icanbwell.com/accessToken",
                                    },
                                ]
                            },
                            "diagnostics": '{"url": '
                            '"http://mock-server:1080/test_fhir_simulated_graph_with_operation_outcomes_async/MedicationRequest?patient=1", '
                            '"error": "NotFound", '
                            '"status": 404, '
                            '"extra_context_to_return": '
                            '{"service_slug": '
                            '"medstar"}, "accessToken": '
                            '"my_access_token", '
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
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_with_operation_outcomes_async/MedicationDispense?patient=1",
                },
                "resource": {
                    "issue": [
                        {
                            "code": "not-found",
                            "details": {
                                "coding": [
                                    {
                                        "code": "http://mock-server:1080/test_fhir_simulated_graph_with_operation_outcomes_async/MedicationDispense?patient=1",
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
                                    {
                                        "code": "my_access_token",
                                        "system": "https://www.icanbwell.com/accessToken",
                                    },
                                ]
                            },
                            "diagnostics": '{"url": '
                            '"http://mock-server:1080/test_fhir_simulated_graph_with_operation_outcomes_async/MedicationDispense?patient=1", '
                            '"error": "NotFound", '
                            '"status": 404, '
                            '"extra_context_to_return": '
                            '{"service_slug": '
                            '"medstar"}, "accessToken": '
                            '"my_access_token", '
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

    bundle = json.loads(response.responses)
    assert bundle == expected_json
