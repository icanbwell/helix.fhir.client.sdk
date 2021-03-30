import requests_mock

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.fhir_request_response import FhirRequestResponse


def test_fhir_client_patient_list_auth_fail() -> None:
    adapter = requests_mock.Adapter()
    url = "http://foo"
    adapter.register_uri("GET", f"{url}/Patient", status_code=403)

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(url).resource("Patient")
    fhir_client = fhir_client.adapter(adapter)
    response: FhirRequestResponse = fhir_client.send_request()

    print(response.responses)
    assert response.error == "403"
