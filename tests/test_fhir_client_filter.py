from typing import Any, Dict, List, Optional

import requests_mock

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.filters.identifier_filter import IdentifierFilter
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


def test_fhir_client_filter() -> None:
    with requests_mock.Mocker() as mock:
        url = "http://foo"
        response_text_1 = {
            "resourceType": "Bundle",
            "total": 2,
            "entry": [{"resource": {"resourceType": "Patient", "id": "1"}}],
        }
        mock.get(
            f"{url}/Patient?_count=10&_getpagesoffset=0&_total=accurate"
            "&identifier=http://hl7.org/fhir/sid/us-npi|1487831681",
            json=response_text_1,
        )
        response_text_2 = {
            "resourceType": "Bundle",
            "total": 2,
            "entry": [{"resource": {"resourceType": "Patient", "id": "2"}}],
        }
        mock.get(
            f"{url}/Patient?_count=10&_getpagesoffset=1&_total=accurate"
            "&identifier=http://hl7.org/fhir/sid/us-npi|1487831681",
            json=response_text_2,
        )
        # mock running out of resources
        response_text_3 = {"resourceType": "Bundle", "total": 2, "entry": []}
        mock.get(
            f"{url}/Patient?_count=10&_getpagesoffset=2&_total=accurate"
            "&identifier=http://hl7.org/fhir/sid/us-npi|1487831681",
            json=response_text_3,
        )

        fhir_client = FhirClient()
        fhir_client = fhir_client.url(url).resource("Patient")
        fhir_client = fhir_client.page_size(10)
        fhir_client = fhir_client.include_total(True)
        fhir_client = fhir_client.filter(
            [
                IdentifierFilter(
                    system="http://hl7.org/fhir/sid/us-npi", value="1487831681"
                )
            ]
        )

        def handle_batch(x: Optional[List[Dict[str, Any]]]) -> bool:
            if x:
                resources_list.extend(x)
            return True

        resources_list: List[Dict[str, Any]] = []
        response: FhirGetResponse = fhir_client.get_in_batches(
            fn_handle_batch=handle_batch
        )

        print(response.responses)
        assert response.responses == "[]"

        assert response.total_count == 2

        print(resources_list)
        assert resources_list == [
            response_text_1["entry"][0]["resource"],  # type: ignore
            response_text_2["entry"][0]["resource"],  # type: ignore
        ]
