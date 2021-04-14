from typing import Any, Optional

import requests
import requests_mock
from requests import Response

from helix_fhir_client_sdk.fhir_client import FhirClient


def test_fhir_client_patient_delete() -> None:
    with requests_mock.Mocker() as mock:
        # Arrange
        url = "http://foo"

        def delete_matcher(request: Any) -> Optional[Response]:
            if request.path == "/patient/12345":
                resp: Response = requests.Response()
                resp.status_code = 204
                return resp
            return None

        mock.add_matcher(delete_matcher)

        # Act
        fhir_client = FhirClient()
        fhir_client = fhir_client.url(url).resource("Patient").id_("12345")
        response: Response = fhir_client.delete()

        # Assert
        response.raise_for_status()
        assert response.status_code == 204
