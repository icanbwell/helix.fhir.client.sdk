import json

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse
from tests_integration.common import clean_fhir_server


async def test_dev_server_get_patients_error() -> None:
    clean_fhir_server()

    url = "http://fhir:3000/4_0_0"
    fhir_client = FhirClient()
    fhir_client = fhir_client.url(url).resource("Patient")
    await fhir_client.id_("12356").delete_async()

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(url).resource("Patient")
    resource = {
        "resourceType": "Patient",
        "id": "12356",
        "meta": "bad",
    }
    merge_response: FhirMergeResponse = await fhir_client.merge_async(
        json_data_list=[json.dumps(resource)]
    )
    print(merge_response.responses)
    assert merge_response.status == 200, merge_response.responses
    assert merge_response.request_id is not None
    assert merge_response.responses[0]["issue"] is not None, json.dumps(
        merge_response.responses
    )
