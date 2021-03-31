import pytest
import requests_mock

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


def test_fhir_client_patient_list_auth_fail() -> None:
    with requests_mock.Mocker() as mock:
        url = "http://foo"
        mock.get(f"{url}/Patient", status_code=403)

        fhir_client = FhirClient()
        fhir_client = fhir_client.url(url).resource("Patient")

        with pytest.raises(AssertionError):
            response: FhirGetResponse = fhir_client.get()

            print(response.responses)
            assert response.error == "403"
