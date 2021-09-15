import json
from typing import Any, Optional

import requests
import requests_mock
from requests import Response

from helix_fhir_client_sdk.fhir_client import FhirClient


def test_fhir_client_patient_update() -> None:
    with requests_mock.Mocker() as mock:
        url = "http://foo"
        request_data = {"resourceType": "Patient", "id": "12355"}
        response_json = [{"created": 1, "updated": 0}]

        def custom_matcher(request: Any) -> Optional[Response]:
            if request.path == "/patient/12355" and request.text == json.dumps(
                request_data
            ):
                resp: Response = requests.Response()
                resp.status_code = 200
                return resp
            return None

        mock.put(
            f"{url}/Patient/12355",
            additional_matcher=custom_matcher,
            text=f"{json.dumps(response_json)}",
        )

        fhir_client = FhirClient()
        fhir_client = fhir_client.url(url).resource("Patient")
        fhir_client = fhir_client.id_(request_data["id"])
        response: Response = fhir_client.update(json.dumps(request_data))

        assert response.ok
