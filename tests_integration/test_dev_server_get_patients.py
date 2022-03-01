import json

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse
from tests_integration.common import clean_fhir_server


def test_dev_server_get_patients() -> None:
    clean_fhir_server()

    url = "http://fhir:3000/4_0_0"
    fhir_client = FhirClient()
    fhir_client = fhir_client.url(url).resource("Patient")
    resource = {
        "resourceType": "Patient",
        "id": "12355",
        "meta": {
            "security": [
                {"system": "https://www.icanbwell.com/access", "code": "bwell"}
            ]
        },
    }
    merge_response: FhirMergeResponse = fhir_client.merge([json.dumps(resource)])
    print(merge_response.responses)
    assert merge_response.status == 200, merge_response.responses
    assert merge_response.responses[0]["created"] is True, merge_response.responses
    fhir_client = fhir_client.url(url).resource("Patient")
    response: FhirGetResponse = fhir_client.get()
    print(response.responses)
    responses_ = json.loads(response.responses)[0]
    assert responses_["id"] == resource["id"]
    assert responses_["resourceType"] == resource["resourceType"]
