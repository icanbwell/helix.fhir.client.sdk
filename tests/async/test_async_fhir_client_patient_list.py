import json

from aioresponses import aioresponses

from helix_fhir_client_sdk.async_fhir_client import AsyncFhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


async def test_async_fhir_client_patient_list() -> None:
    mock: aioresponses
    with aioresponses() as mock:  # type: ignore
        url = "http://foo"
        response_text = {"resourceType": "Patient", "id": "12355"}
        mock.get(f"{url}/Patient", payload=response_text)

        fhir_client = AsyncFhirClient()
        fhir_client = fhir_client.url(url).resource("Patient")
        response: FhirGetResponse = await fhir_client.get()

        print(response.responses)
        assert response.responses == json.dumps(response_text)
