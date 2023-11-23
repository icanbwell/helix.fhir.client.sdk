import json
from typing import Optional, List

from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


async def test_async_fhir_client_patient_list_auth_fail_retry_custom_refresh_function() -> None:
    test_name = (
        "test_async_fhir_client_patient_list_auth_fail_retry_custom_refresh_function"
    )

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(
        base_url=mock_server_url
    )

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
    fhir_client = fhir_client.client_credentials(
        client_id="client_id", client_secret="client_secret"
    )
    fhir_client = fhir_client.auth_server_url(absolute_url + "/" + "auth").auth_scopes(
        ["user/*.ready"]
    )

    async def my_authenticate_async(
        auth_server_url: str,
        auth_scopes: Optional[List[str]],
        login_token: Optional[str],
    ) -> Optional[str]:
        assert auth_server_url
        assert auth_scopes
        assert login_token
        return "my_access_token"

    fhir_client = fhir_client.refresh_token_function(my_authenticate_async)
    response: FhirGetResponse = await fhir_client.get_async()

    print(response.responses)
    assert response.responses == response_text
