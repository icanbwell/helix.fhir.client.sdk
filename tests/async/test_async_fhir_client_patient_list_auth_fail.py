from logging import Logger

from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from tests.logger_for_test import LoggerForTest


async def test_fhir_client_patient_list_auth_fail_async() -> None:
    logger: Logger = LoggerForTest()
    test_name = "test_fhir_client_patient_list_auth_fail_async"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(base_url=mock_server_url)

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    mock_client.expect(
        request=mock_request(path=f"/{relative_url}/Patient", method="GET"),
        response=mock_response(code=403),
        timing=times(1),
    )

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(absolute_url).resource("Patient")

    response: FhirGetResponse = await fhir_client.get_async()

    logger.info(response.get_response_text())
    assert response.status == 403
