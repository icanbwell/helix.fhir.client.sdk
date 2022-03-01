import json

from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


def test_fhir_client_patient_by_id() -> None:
    test_name = "test_fhir_client_patient_by_id"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(
        base_url=mock_server_url
    )

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    response_text: str = json.dumps({"resourceType": "Patient", "id": "12355"})
    mock_client.expect(
        mock_request(path=f"/{relative_url}/Patient/12355", method="GET"),
        mock_response(body=response_text),
        timing=times(1),
    )

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(absolute_url).resource("Patient").id_("12355")
    response: FhirGetResponse = fhir_client.get()

    print(response.responses)
    assert response.responses == response_text
