import json

import requests_mock

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


def test_fhir_client_patient_list() -> None:
    with requests_mock.Mocker() as mock:
        url = "http://foo"
        response_text = {"resourceType": "Patient", "id": "12355"}
        mock.get(f"{url}/Patient", json=response_text)

        fhir_client = FhirClient()
        fhir_client = fhir_client.url(url).resource("Patient")
        response: FhirGetResponse = fhir_client.get()

        print(response.responses)
        assert response.responses == json.dumps(response_text)
