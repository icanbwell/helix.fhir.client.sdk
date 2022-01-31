import pytest
from aioresponses import aioresponses

from helix_fhir_client_sdk.async_fhir_client import AsyncFhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


async def test_async_fhir_client_patient_list_auth_fail() -> None:
    mock: aioresponses
    with aioresponses() as mock:  # type: ignore
        url = "http://foo"
        mock.get(f"{url}/Patient", status=403)

        fhir_client = AsyncFhirClient()
        fhir_client = fhir_client.url(url).resource("Patient")

        with pytest.raises(AssertionError):
            response: FhirGetResponse = await fhir_client.get()

            print(response.responses)
            assert response.error == "403"
