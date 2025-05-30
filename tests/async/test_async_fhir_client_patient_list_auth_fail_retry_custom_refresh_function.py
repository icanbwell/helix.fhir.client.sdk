import json
from logging import Logger
from unittest.mock import AsyncMock

from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.function_types import RefreshTokenResult
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from tests.logger_for_test import LoggerForTest


async def test_async_fhir_client_patient_list_auth_fail_retry_custom_refresh_function() -> None:
    logger: Logger = LoggerForTest()
    test_name = "test_async_fhir_client_patient_list_auth_fail_retry_custom_refresh_function"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(base_url=mock_server_url)

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    mock_client.expect(
        request=mock_request(path=f"/{relative_url}/Patient", method="GET"),
        response=mock_response(code=401),
        timing=times(1),
    )

    response_text: str = json.dumps({"resourceType": "Patient", "id": "12355"})
    mock_client.expect(
        request=mock_request(path=f"/{relative_url}/Patient", method="GET"),
        response=mock_response(body=response_text),
        timing=times(1),
    )

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(absolute_url).resource("Patient")
    fhir_client = fhir_client.client_credentials(client_id="client_id", client_secret="client_secret")
    fhir_client = fhir_client.auth_server_url(absolute_url + "/" + "auth").auth_scopes(["user/*.ready"])

    mocked_authenticate_async = AsyncMock()
    mocked_authenticate_async.return_value = RefreshTokenResult(
        access_token="my_access_token", expiry_date=None, abort_request=False
    )

    fhir_client = fhir_client.refresh_token_function(mocked_authenticate_async)
    response: FhirGetResponse = await fhir_client.get_async()

    mocked_authenticate_async.assert_called()
    mocked_authenticate_async.assert_called_with(
        url="http://mock-server:1080/test_async_fhir_client_patient_list_auth_fail_retry_custom_refresh_function/Patient",
        status_code=401,
        current_token=None,
        expiry_date=None,
        retry_count=0,
    )
    logger.info(response.get_response_text())
    assert response.get_response_text() == response_text
