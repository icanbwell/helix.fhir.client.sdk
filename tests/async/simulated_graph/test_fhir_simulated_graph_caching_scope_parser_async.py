import json
from pathlib import Path
from typing import Dict, Any, Optional

from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient

from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from tests.logger_for_test import LoggerForTest


async def test_fhir_simulated_graph_caching_scope_parser_async() -> None:
    print("")
    data_dir: Path = Path(__file__).parent.joinpath("./")
    graph_json: Dict[str, Any]
    with open(data_dir.joinpath("graphs").joinpath("provider.json"), "r") as file:
        contents = file.read()
        graph_json = json.loads(contents)

    test_name = "test_fhir_simulated_graph_caching_scope_parser_async"

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

    response_text = {
        "entry": [
            {
                "resource": {
                    "resourceType": "Encounter",
                    "id": "8",
                    "participant": [
                        {"individual": {"reference": "Practitioner/12345"}}
                    ],
                }
            },
            {
                "resource": {
                    "resourceType": "Encounter",
                    "id": "10",
                    "participant": [
                        {"individual": {"reference": "Practitioner/12345"}}
                    ],
                }
            },
        ]
    }
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Encounter",
            querystring={"patient": "1"},
            method="GET",
        ),
        response=mock_response(body=response_text),
        timing=times(1),
    )

    response_text = {
        "entry": [{"resource": {"resourceType": "Practitioner", "id": "12345"}}]
    }
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Practitioner/12345",
            method="GET",
        ),
        response=mock_response(body=response_text),
        timing=times(1),
    )

    logger = LoggerForTest()
    fhir_client = FhirClient()
    fhir_client = fhir_client.expand_fhir_bundle(False)
    fhir_client.logger(logger=logger)
    fhir_client.auth_scopes(
        # include other resources but skip Observation and Encounter
        auth_scopes=[
            "patient/Patient.read",
            "patient/AllergyIntolerance.read",
            "patient/Practitioner.read patient/Organization.read",
            "patient/Coverage.read",
            "launch/patient",
        ]
    )

    fhir_client.extra_context_to_return({"service_slug": "medstar"})

    auth_access_token = "my_access_token"
    if auth_access_token:
        fhir_client = fhir_client.set_access_token(auth_access_token)

    fhir_client = fhir_client.url(absolute_url).resource("Patient")
    response: Optional[FhirGetResponse] = await FhirGetResponse.from_async_generator(
        fhir_client.simulate_graph_streaming_async(
            id_="1",
            graph_json=graph_json,
            contained=False,
            separate_bundle_resources=False,
        )
    )
    assert response is not None
    print(response.responses)

    expected_json: Dict[str, Any] = {
        "entry": [
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_caching_scope_parser_async/Patient/1",
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
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_caching_scope_parser_async/Practitioner/5",
                },
                "resource": {"id": "5", "resourceType": "Practitioner"},
                "response": {"status": "200"},
            },
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_caching_scope_parser_async/Organization/6",
                },
                "resource": {"id": "6", "resourceType": "Organization"},
                "response": {"status": "200"},
            },
        ]
    }

    bundle: Dict[str, Any]
    try:
        bundle = json.loads(response.responses)
    except Exception as e:
        raise Exception(
            f"Unable to parse result json: {e}: {response.responses}"
        ) from e

    bundle["entry"] = [
        e
        for e in bundle["entry"]
        if e["resource"]["resourceType"] != "OperationOutcome"
    ]

    bundle["entry"] = sorted(
        bundle["entry"],
        key=lambda x: x["resource"]["resourceType"] + x["resource"]["id"],
    )
    expected_json["entry"] = sorted(
        expected_json["entry"],
        key=lambda x: x["resource"]["resourceType"] + x["resource"]["id"],
    )
    assert bundle == expected_json
