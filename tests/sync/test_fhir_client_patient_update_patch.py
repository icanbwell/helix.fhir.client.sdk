import json

from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_update_response import FhirUpdateResponse


async def test_fhir_client_patient_update() -> None:
    test_name = "test_fhir_client_patient_update_using_patch"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(base_url=mock_server_url)

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    response_text_1: dict[str, int] = {"created": 0, "updated": 1}
    resource = [{"op": "replace", "path": "/gender", "value": "male"}]

    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Patient/1234",
            method="PATCH",
            body=json.dumps(resource),
        ),
        response=mock_response(body=json.dumps(response_text_1)),
        timing=times(1),
    )
    fhir_client = FhirClient()
    fhir_client = fhir_client.url(absolute_url).resource("Patient").id_("1234")
    response: FhirUpdateResponse = await fhir_client.send_patch_request_async(json.dumps(resource))

    assert response.status == 200
