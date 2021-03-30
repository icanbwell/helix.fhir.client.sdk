import json

import requests_mock

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.fhir_request_response import FhirRequestResponse


def test_fhir_client_patient_by_id() -> None:
    with requests_mock.Mocker() as mock:
        url = "http://foo"
        response_text = {"resourceType": "Patient", "id": "12355"}
        mock.get(f"{url}/Patient/12355", json=response_text)

        fhir_client = FhirClient()
        fhir_client = fhir_client.url(url).resource("Patient").id_("12355")
        response: FhirRequestResponse = fhir_client.get()

        print(response.responses)
        assert response.responses == [json.dumps(response_text)]
