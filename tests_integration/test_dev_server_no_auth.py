from helix_fhir_client_sdk.async_fhir_client import AsyncFhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


def test_dev_server_no_auth() -> None:
    url = "https://fhir.dev.bwell.zone/4_0_0"
    fhir_client = AsyncFhirClient()
    fhir_client = fhir_client.url(url).resource("Patient")
    response: FhirGetResponse = fhir_client.get()
    print(response.responses)
