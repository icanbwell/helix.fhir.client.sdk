import json
from typing import Any, List

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse
from tests_integration.common import clean_fhir_server


async def test_dev_server_get_patients() -> None:
    clean_fhir_server()

    url = "http://fhir:3000/4_0_0"
    fhir_client = FhirClient()
    fhir_client = fhir_client.url(url).resource("Patient")
    await fhir_client.id_("12355").delete_async()

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(url).use_data_streaming(True).resource("Patient")
    resource = {
        "resourceType": "Patient",
        "id": "12355",
        "meta": {
            "source": "http://www.icanbwell.com",
            "security": [
                {"system": "https://www.icanbwell.com/access", "code": "bwell"},
                {"system": "https://www.icanbwell.com/owner", "code": "bwell"},
            ],
        },
    }
    merge_response: FhirMergeResponse = await fhir_client.merge_async(
        json_data_list=[json.dumps(resource)]
    )
    print(merge_response.responses)
    assert merge_response.status == 200, merge_response.responses
    assert merge_response.responses[0]["created"] is True, merge_response.responses
    fhir_client = fhir_client.url(url).resource("Patient")
    response: FhirGetResponse = await fhir_client.get_async()
    response_text = response.responses
    bundle = json.loads(response_text)
    responses_: List[Any] = [r["resource"] for r in bundle["entry"]]
    assert len(responses_) == 1
    assert responses_[0]["id"] == resource["id"]
    assert responses_[0]["resourceType"] == resource["resourceType"]
