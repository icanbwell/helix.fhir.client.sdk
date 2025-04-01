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


async def test_fhir_simulated_graph_with_operation_outcomes_async() -> None:
    print("")
    data_dir: Path = Path(__file__).parent.joinpath("./")
    graph_json: Dict[str, Any]
    with open(data_dir.joinpath("graphs").joinpath("aetna.json"), "r") as file:
        contents = file.read()
        graph_json = json.loads(contents)

    test_name = test_fhir_simulated_graph_with_operation_outcomes_async.__name__

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

    fhir_client = fhir_client.set_create_operation_outcome_for_error(True)

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
    print(response.get_response_text())

    expected_file_path = data_dir.joinpath("expected")
    with open(expected_file_path.joinpath(test_name + ".json")) as f:
        expected_json = json.load(f)

    bundle = json.loads(response.get_response_text())
    # sort the entries by request url
    bundle["entry"] = sorted(
        bundle["entry"],
        key=lambda x: (
            int(x["resource"].get("id"))
            if x["resource"].get("id")
            else hash(x["request"]["url"])
        ),
    )
    expected_json["entry"] = sorted(
        expected_json["entry"],
        key=lambda x: (
            int(x["resource"].get("id"))
            if x["resource"].get("id")
            else hash(x["request"]["url"])
        ),
    )
    assert bundle == expected_json
