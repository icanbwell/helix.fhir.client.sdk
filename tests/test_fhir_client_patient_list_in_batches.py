from typing import Any, Dict, List

import requests_mock

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


def test_fhir_client_patient_list_in_batches() -> None:
    with requests_mock.Mocker() as mock:
        url = "http://foo"
        response_text_1 = [{"resourceType": "Patient", "id": "12355"}]
        mock.get(f"{url}/Patient?_count=10&_getpagesoffset=0", json=response_text_1)
        response_text_2 = [{"resourceType": "Patient", "id": "2"}]
        mock.get(f"{url}/Patient?_count=10&_getpagesoffset=1", json=response_text_2)
        # mock running out of resources
        mock.get(f"{url}/Patient?_count=10&_getpagesoffset=2", json=[])

        fhir_client = FhirClient()
        fhir_client = fhir_client.url(url).resource("Patient")
        fhir_client = fhir_client.page_size(10)

        resources_list: List[Dict[str, Any]] = []
        response: FhirGetResponse = fhir_client.get_in_batches(
            fn_handle_batch=lambda x: resources_list.extend(x)
        )

        print(response.responses)
        assert response.responses == "[]"

        print(resources_list)
        assert resources_list == response_text_1 + response_text_2
