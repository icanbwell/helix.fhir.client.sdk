from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)
from requests import Response

from helix_fhir_client_sdk.fhir_client import FhirClient


def test_fhir_client_patient_delete() -> None:
    test_name = "test_fhir_client_patient_by_id"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(
        base_url=mock_server_url
    )

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    mock_client.expect(
        mock_request(path=f"/{relative_url}/Patient/12345", method="DELETE"),
        mock_response(code=204),
        timing=times(1),
    )

    # Act
    fhir_client = FhirClient()
    fhir_client = fhir_client.url(absolute_url).resource("Patient").id_("12345")
    response: Response = fhir_client.delete()

    # Assert
    response.raise_for_status()
    assert response.status_code == 204
