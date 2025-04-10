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


async def test_fhir_simulated_graph_multiple_graph_in_one_call_async() -> None:
    print("")
    data_dir: Path = Path(__file__).parent.joinpath("./")
    graph_json: Dict[str, Any]
    with open(data_dir.joinpath("graphs").joinpath("aetna.json"), "r") as file:
        contents = file.read()
        graph_json = json.loads(contents)

    test_name = "test_fhir_simulated_graph_multiple_graph_in_one_call_async"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(
        base_url=mock_server_url
    )

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    response_text: Dict[str, Any]

    response_text = {
        "entry": [
            {
                "resource": {"id": "1", "resourceType": "Practitioner"},
            },
            {"resource": {"id": "2", "resourceType": "Practitioner"}},
        ]
    }

    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Practitioner",
            method="GET",
            querystring={"_id": "1,2"},
        ),
        response=mock_response(body=response_text),
        timing=times(1),
    )

    response_text = {
        "entry": [
            {
                "resource": {
                    "resourceType": "PractitionerRole",
                    "id": "10",
                    "practitioner": {"reference": "Practitioner/1"},
                }
            },
            {
                "resource": {
                    "resourceType": "PractitionerRole",
                    "id": "12",
                    "practitioner": {"reference": "Practitioner/2"},
                }
            },
        ]
    }
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/PractitionerRole",
            method="GET",
            querystring={"practitioner": "1,2"},
        ),
        response=mock_response(body=response_text),
        timing=times(1),
    )

    response_text = {
        "entry": [
            {
                "resource": {
                    "resourceType": "Schedule",
                    "id": "100",
                    "actor": {"reference": "PractitionerRole/10"},
                }
            },
            {
                "resource": {
                    "resourceType": "Schedule",
                    "id": "120",
                    "actor": {"reference": "PractitionerRole/12"},
                }
            },
        ]
    }
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Schedule",
            method="GET",
            querystring={"actor": "10,12"},
        ),
        response=mock_response(body=response_text),
        timing=times(1),
    )

    response_text = {
        "entry": [
            {
                "resource": {
                    "resourceType": "Slot",
                    "id": "1000",
                    "schedule": {"reference": "Schedule/100"},
                }
            },
            {
                "resource": {
                    "resourceType": "Slot",
                    "id": "1200",
                    "schedule": {"reference": "Schedule/120"},
                }
            },
        ]
    }
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Slot",
            method="GET",
            querystring={"schedule": "100,120"},
        ),
        response=mock_response(body=response_text),
        timing=times(1),
    )

    fhir_client = FhirClient()

    fhir_client = fhir_client.log_level("DEBUG")

    fhir_client = fhir_client.expand_fhir_bundle(False)

    fhir_client = fhir_client.url(absolute_url).resource("Patient")
    response: Optional[FhirGetResponse] = await FhirGetResponse.from_async_generator(
        fhir_client.simulate_graph_streaming_async(
            id_="1,2",
            graph_json=graph_json,
            contained=False,
            separate_bundle_resources=False,
            request_size=10,
        )
    )
    assert response is not None
    print(response.get_response_text())

    expected_json = {
        "resourceType": "Bundle",
        "total": 8,
        "type": "collection",
        "entry": [
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_multiple_graph_in_one_call_async/Practitioner?_id=1%2C2",
                },
                "resource": {"id": "1", "resourceType": "Practitioner"},
                "response": {"status": "200"},
            },
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_multiple_graph_in_one_call_async/Practitioner?_id=1%2C2",
                },
                "resource": {"id": "2", "resourceType": "Practitioner"},
                "response": {"status": "200"},
            },
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_multiple_graph_in_one_call_async/PractitionerRole?practitioner=1,2",
                },
                "resource": {
                    "id": "10",
                    "practitioner": {"reference": "Practitioner/1"},
                    "resourceType": "PractitionerRole",
                },
                "response": {"status": "200"},
            },
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_multiple_graph_in_one_call_async/PractitionerRole?practitioner=1,2",
                },
                "resource": {
                    "id": "12",
                    "practitioner": {"reference": "Practitioner/2"},
                    "resourceType": "PractitionerRole",
                },
                "response": {"status": "200"},
            },
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_multiple_graph_in_one_call_async/Schedule?actor=10,12",
                },
                "resource": {
                    "actor": {"reference": "PractitionerRole/10"},
                    "id": "100",
                    "resourceType": "Schedule",
                },
                "response": {"status": "200"},
            },
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_multiple_graph_in_one_call_async/Schedule?actor=10,12",
                },
                "resource": {
                    "actor": {"reference": "PractitionerRole/12"},
                    "id": "120",
                    "resourceType": "Schedule",
                },
                "response": {"status": "200"},
            },
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_multiple_graph_in_one_call_async/Slot?schedule=100,120",
                },
                "resource": {
                    "id": "1000",
                    "resourceType": "Slot",
                    "schedule": {"reference": "Schedule/100"},
                },
                "response": {"status": "200"},
            },
            {
                "request": {
                    "method": "GET",
                    "url": "http://mock-server:1080/test_fhir_simulated_graph_multiple_graph_in_one_call_async/Slot?schedule=100,120",
                },
                "resource": {
                    "id": "1200",
                    "resourceType": "Slot",
                    "schedule": {"reference": "Schedule/120"},
                },
                "response": {"status": "200"},
            },
        ],
    }

    bundle = json.loads(response.get_response_text())
    # sort the entries by resource id
    bundle["entry"] = sorted(bundle["entry"], key=lambda x: int(x["resource"]["id"]))
    assert bundle == expected_json
