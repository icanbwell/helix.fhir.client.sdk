import json

import requests_mock

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


def test_fhir_client_patient_list_auth_fail_retry() -> None:
    with requests_mock.Mocker() as mock:
        url = "http://foo"
        response_text = {"resourceType": "Patient", "id": "12355"}
        mock.get(f"{url}/Patient", [{"status_code": 403}, {"json": response_text}])
        auth_response = {
            "access_token": "my_access_token",
            "expires_in": 86400,
            "token_type": "Bearer",
        }
        mock.post(
            "http://auth",
            [{"status_code": 200}, {"json": auth_response, "status_code": 200}],
        )

        fhir_client = FhirClient()
        fhir_client = fhir_client.url(url).resource("Patient")
        fhir_client = fhir_client.client_credentials(
            client_id="client_id", client_secret="client_secret"
        )
        fhir_client = fhir_client.auth_server_url("http://auth").auth_scopes(
            ["user/*.ready"]
        )
        response: FhirGetResponse = fhir_client.get()

        print(response.responses)
        assert mock.call_count == 4, ",".join([r.url for r in mock.request_history])
        assert response.responses == json.dumps(response_text)
