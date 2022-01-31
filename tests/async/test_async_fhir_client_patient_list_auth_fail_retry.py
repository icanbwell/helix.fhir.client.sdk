import json

from aioresponses import aioresponses

from helix_fhir_client_sdk.async_fhir_client import AsyncFhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


async def test_async_fhir_client_patient_list_auth_fail_retry() -> None:
    mock: aioresponses
    with aioresponses() as mock:  # type: ignore
        url = "http://foo"
        response_text = {"resourceType": "Patient", "id": "12355"}
        mock.get(f"{url}/Patient", status=403, payload=response_text)
        auth_response = {
            "access_token": "my_access_token",
            "expires_in": 86400,
            "token_type": "Bearer",
        }
        mock.post(
            "http://auth", status=200, payload=auth_response,
        )
        mock.post(
            "http://auth", status=200, payload=auth_response,
        )
        mock.post(
            "http://auth", status=200, payload=auth_response,
        )
        mock.post(
            "http://auth", status=200, payload=auth_response,
        )

        mock.get(f"{url}/Patient", payload=response_text)

        fhir_client = AsyncFhirClient()
        fhir_client = fhir_client.url(url).resource("Patient")
        fhir_client = fhir_client.client_credentials(
            client_id="client_id", client_secret="client_secret"
        )
        fhir_client = fhir_client.auth_server_url("http://auth").auth_scopes(
            ["user/*.ready"]
        )
        response: FhirGetResponse = await fhir_client.get()

        print(response.responses)
        # assert mock.call_count == 4, ",".join([r.url for r in mock.request_history])
        assert response.responses == json.dumps(response_text)
