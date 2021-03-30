import pytest
import requests_mock

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.fhir_request_response import FhirRequestResponse


def test_fhir_client_patient_list_auth_fail() -> None:
    with requests_mock.Mocker() as mock:
        url = "http://foo"
        mock.get(f"{url}/Patient", status_code=403)

        fhir_client = FhirClient()
        fhir_client = fhir_client.url(url).resource("Patient")

        with pytest.raises(AssertionError):
            response: FhirRequestResponse = fhir_client.send_request()

            print(response.responses)
            assert response.error == "403"
