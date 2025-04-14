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
from helix_fhir_client_sdk.utilities.cache.request_cache import RequestCache
from tests.logger_for_test import LoggerForTest


async def test_fhir_simulated_graph_caching_async() -> None:
    print("")
    data_dir: Path = Path(__file__).parent.joinpath("./")
    graph_json: Dict[str, Any]
    with open(data_dir.joinpath("graphs").joinpath("provider.json"), "r") as file:
        contents = file.read()
        graph_json = json.loads(contents)

    test_name = test_fhir_simulated_graph_caching_async.__name__

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(
        base_url=mock_server_url
    )

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    response_text: Dict[str, Any] = {
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
        "resourceType": "Bundle",
        "total": 1,
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "DocumentReference",
                    "id": "11",
                    "content": [
                        {"attachment": {"url": "Binary/12"}},
                        {"attachment": {"url": "Binary/13"}},
                        {"attachment": {"url": "Binary/14"}},
                        {"attachment": {"url": "Binary/15"}},
                    ],
                }
            }
        ],
    }
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/DocumentReference",
            querystring={
                "patient": "1",
            },
            method="GET",
        ),
        response=mock_response(body=response_text),
        timing=times(1),
    )

    # Mock request to return 403 so that Binaries could be fetched one by one
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Binary",
            querystring={
                "_id": "12,13",
            },
            method="GET",
        ),
        response=mock_response(code=403),
        timing=times(1),
    )

    response_text = {"entry": [{"resource": {"resourceType": "Binary", "id": "12"}}]}
    mock_client.expect(
        request=mock_request(path=f"/{relative_url}/Binary/12", method="GET"),
        response=mock_response(body=response_text),
        timing=times(1),
    )
    response_text = {"entry": [{"resource": {"resourceType": "Binary", "id": "13"}}]}
    mock_client.expect(
        request=mock_request(path=f"/{relative_url}/Binary/13", method="GET"),
        response=mock_response(body=response_text),
        timing=times(1),
    )

    response_text = {"entry": [{"resource": {"resourceType": "Binary", "id": "14"}}]}
    mock_client.expect(
        request=mock_request(path=f"/{relative_url}/Binary/14", method="GET"),
        response=mock_response(body=response_text),
        timing=times(1),
    )
    response_text = {"entry": [{"resource": {"resourceType": "Binary", "id": "15"}}]}
    mock_client.expect(
        request=mock_request(path=f"/{relative_url}/Binary/15", method="GET"),
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

    response_text = {"resourceType": "Practitioner", "id": "12345"}
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

    fhir_client.extra_context_to_return({"service_slug": "medstar"})

    auth_access_token = "my_access_token"
    if auth_access_token:
        fhir_client = fhir_client.set_access_token(auth_access_token)

    request_cache = RequestCache(clear_cache_at_the_end=False)

    fhir_client = fhir_client.url(absolute_url).resource("Patient")
    response: Optional[FhirGetResponse] = await FhirGetResponse.from_async_generator(
        fhir_client.simulate_graph_streaming_async(
            id_="1",
            graph_json=graph_json,
            contained=False,
            separate_bundle_resources=False,
            request_size=2,
            input_cache=request_cache,
        )
    )
    assert response is not None
    text = response.get_response_text()
    print(text)

    print("---------- Request Cache ----------")
    async for entry in request_cache.get_entries_async():
        print(entry)
    print("---------- End Request Cache ----------")

    expected_file_path = data_dir.joinpath("expected")
    with open(expected_file_path.joinpath(test_name + ".json")) as f:
        expected_json = json.load(f)

    bundle = json.loads(text)
    bundle["entry"] = [
        e
        for e in bundle["entry"]
        if e["resource"]["resourceType"] != "OperationOutcome"
    ]

    # diff = DeepDiff(bundle, expected_json, ignore_order=True)
    # assert not diff, f"Diff: {diff}"

    # sort the entries by request url
    bundle["entry"] = sorted(bundle["entry"], key=lambda x: int(x["resource"]["id"]))
    bundle["total"] = len(bundle["entry"])
    print(bundle)
    assert bundle == expected_json
