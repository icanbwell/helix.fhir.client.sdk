import json
from typing import Dict, List

from aiohttp import ClientResponse
from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.async_fhir_client import AsyncFhirClient


async def test_fhir_client_patient_update_async() -> None:
    test_name = "test_fhir_client_patient_merge_async"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(
        base_url=mock_server_url
    )

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    response_text_1: List[Dict[str, int]] = [{"created": 1, "updated": 0}]
    resource = {"resourceType": "Patient", "id": "12355"}
    # request_body = {"resourceType": "Bundle", "entry": [{"resource": resource}]}
    mock_client.expect(
        mock_request(
            path=f"/{relative_url}/Patient/12355",
            method="PUT",
            body=json.dumps(resource),
        ),
        mock_response(body=json.dumps(response_text_1)),
        timing=times(1),
    )

    fhir_client = AsyncFhirClient()
    fhir_client = fhir_client.url(absolute_url).resource("Patient")
    fhir_client = fhir_client.id_(resource["id"])
    response: ClientResponse = await fhir_client.update_async(json.dumps(resource))

    assert response.ok
