import json
from os import environ
from typing import Optional

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse
from helix_fhir_client_sdk.utilities.fhir_server_helpers import FhirServerHelpers


async def test_async_real_fhir_server_get_patients_error() -> None:
    await FhirServerHelpers.clean_fhir_server_async(resource_type="Patient")

    fhir_server_url: str = environ["FHIR_SERVER_URL"]
    auth_client_id = environ["FHIR_CLIENT_ID"]
    auth_client_secret = environ["FHIR_CLIENT_SECRET"]
    auth_well_known_url = environ["AUTH_CONFIGURATION_URI"]

    fhir_client = FhirClient()
    fhir_client = fhir_client.client_credentials(
        client_id=auth_client_id, client_secret=auth_client_secret
    )
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)
    fhir_client = fhir_client.url(fhir_server_url).resource("Patient")
    await fhir_client.id_("12356").delete_async()

    fhir_client = FhirClient()
    fhir_client = fhir_client.client_credentials(
        client_id=auth_client_id, client_secret=auth_client_secret
    )
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)
    fhir_client = fhir_client.url(fhir_server_url).resource("Patient")
    resource = {
        "resourceType": "Patient",
        "id": "12356",
        "meta": "bad",
    }
    merge_response: Optional[FhirMergeResponse] = (
        await FhirMergeResponse.from_async_generator(
            fhir_client.merge_async(json_data_list=[json.dumps(resource)])
        )
    )
    assert merge_response is not None
    print(merge_response.responses)
    assert merge_response.status == 200, merge_response.responses
    assert merge_response.request_id is not None
    assert merge_response.responses[0]["issue"] is not None, json.dumps(
        merge_response.responses
    )
