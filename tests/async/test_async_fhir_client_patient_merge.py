import json
from typing import Dict, List

from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse


async def test_fhir_client_patient_merge_async() -> None:
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
            path=f"/{relative_url}/Patient/1/$merge",
            method="POST",
            body=json.dumps(resource),
        ),
        mock_response(body=json.dumps(response_text_1)),
        timing=times(1),
    )

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(absolute_url).resource("Patient")
    response: FhirMergeResponse = await fhir_client.merge_async(
        json_data_list=[json.dumps(resource)]
    )

    print(response.responses)
    assert response.responses == response_text_1
