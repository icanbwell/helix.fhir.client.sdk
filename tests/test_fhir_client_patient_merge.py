import json

import requests_mock

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse


def test_fhir_client_patient_merge() -> None:
    with requests_mock.Mocker() as mock:
        url = "http://foo"
        request_data = {"resourceType": "Patient", "id": "12355"}
        response_json = [{"created": 1, "updated": 0}]
        mock.post(f"{url}/Patient/1/$merge", json=response_json)

        fhir_client = FhirClient()
        fhir_client = fhir_client.url(url).resource("Patient")
        response: FhirMergeResponse = fhir_client.merge([json.dumps(request_data)])

        print(response.responses)
        assert response.responses == response_json
