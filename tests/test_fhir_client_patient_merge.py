import json
from typing import Any, Optional

import requests
import requests_mock
from requests import Response

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse


def test_fhir_client_patient_merge() -> None:
    with requests_mock.Mocker() as mock:
        url = "http://foo"
        request_data = {"resourceType": "Patient", "id": "12355"}
        response_json = [{"created": 1, "updated": 0}]

        def custom_matcher(request: Any) -> Optional[Response]:
            if request.path == "/patient/1/$merge" and request.text == json.dumps(
                [request_data]
            ):
                resp: Response = requests.Response()
                resp.status_code = 200
                return resp
            return None

        mock.post(
            f"{url}/Patient/1/$merge",
            additional_matcher=custom_matcher,
            text=f"{json.dumps(response_json)}",
        )

        fhir_client = FhirClient()
        fhir_client = fhir_client.url(url).resource("Patient")
        response: FhirMergeResponse = fhir_client.merge([json.dumps(request_data)])

        print(response.responses)
        assert response.responses == response_json
