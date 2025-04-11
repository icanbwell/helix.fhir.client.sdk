import pytest

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


@pytest.mark.skip("for talking to production")
def test_dev_server_auth() -> None:
    url = "https://fhir-auth.dev.bwell.zone/4_0_0"
    fhir_client = FhirClient()
    fhir_client = fhir_client.url(url).resource("Patient")
    fhir_client = fhir_client.client_credentials(
        client_id="",
        client_secret="",
    ).auth_scopes(["user/*.read"])
    response: FhirGetResponse = fhir_client.get()
    print(response.get_response_text())
