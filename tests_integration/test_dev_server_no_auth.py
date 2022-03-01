import pytest

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


@pytest.mark.skip("for talking to production")
def test_dev_server_no_auth() -> None:
    url = "http://fhir:3000/4_0_0"
    fhir_client = FhirClient()
    fhir_client = fhir_client.url(url).resource("Patient")
    response: FhirGetResponse = fhir_client.get()
    print(response.responses)
