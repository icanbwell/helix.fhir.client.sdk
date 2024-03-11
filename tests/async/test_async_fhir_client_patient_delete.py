from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_delete_response import FhirDeleteResponse


async def test_fhir_client_patient_delete_async() -> None:
    test_name = "test_fhir_client_patient_delete_async"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(
        base_url=mock_server_url
    )

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    mock_client.expect(
        request=mock_request(path=f"/{relative_url}/Patient/12345", method="DELETE"),
        response=mock_response(code=204),
        timing=times(1),
    )
    additional_request_headers = {
        "TestHeaderOne": "abcdtest",
        "User-Agent": "TestPipelineName",
    }

    # Act
    fhir_client = FhirClient()
    fhir_client = fhir_client.url(absolute_url).resource("Patient").id_("12345")
    fhir_client = fhir_client.additional_request_headers(additional_request_headers)
    response: FhirDeleteResponse = await fhir_client.delete_async()

    # Assert
    assert response.status == 204
