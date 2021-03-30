import json

import requests_mock

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.fhir_request_response import FhirRequestResponse


def test_fhir_client_patient_by_id() -> None:
    adapter = requests_mock.Adapter()
    url = "http://foo"
    response_text = {"resourceType": "Patient", "id": "12355"}
    adapter.register_uri("GET", f"{url}/Patient/12355", text=json.dumps(response_text))

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(url).resource("Patient").id_("12355")
    fhir_client = fhir_client.adapter(adapter)
    response: FhirRequestResponse = fhir_client.send_request()

    print(response.responses)
    assert response.responses == [json.dumps(response_text)]
