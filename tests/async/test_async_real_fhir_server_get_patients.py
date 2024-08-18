import json
from os import environ
from typing import Any, List, Dict, Optional

import pytest

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse
from helix_fhir_client_sdk.utilities.fhir_server_helpers import FhirServerHelpers


@pytest.mark.parametrize("use_data_streaming", [True, False])
async def test_async_real_fhir_server_get_patients(use_data_streaming: bool) -> None:
    print()
    await FhirServerHelpers.clean_fhir_server_async(resource_type="Patient")

    environ["LOGLEVEL"] = "DEBUG"

    fhir_server_url: str = environ["FHIR_SERVER_URL"]
    auth_client_id = environ["FHIR_CLIENT_ID"]
    auth_client_secret = environ["FHIR_CLIENT_SECRET"]
    auth_well_known_url = environ["AUTH_CONFIGURATION_URI"]

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(fhir_server_url).resource("Patient")
    fhir_client = fhir_client.client_credentials(
        client_id=auth_client_id, client_secret=auth_client_secret
    )
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)
    resource = {
        "resourceType": "Patient",
        "id": "12355",
        "meta": {
            "source": "http://www.icanbwell.com",
            "security": [
                {"system": "https://www.icanbwell.com/access", "code": "bwell"},
                {"system": "https://www.icanbwell.com/owner", "code": "bwell"},
            ],
        },
    }
    merge_response: Optional[FhirMergeResponse] = (
        await FhirMergeResponse.from_async_generator(
            fhir_client.merge_async(json_data_list=[json.dumps(resource)])
        )
    )
    assert merge_response is not None
    print(merge_response.responses)
    assert merge_response.status == 200, merge_response.responses
    assert len(merge_response.responses) == 1, merge_response.responses
    assert merge_response.responses[0]["created"] is True, merge_response.responses

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(fhir_server_url).resource("Patient")
    fhir_client = fhir_client.client_credentials(
        client_id=auth_client_id, client_secret=auth_client_secret
    )
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)
    fhir_client = fhir_client.expand_fhir_bundle(False)
    fhir_client = fhir_client.use_data_streaming(use_data_streaming)
    response: FhirGetResponse = await fhir_client.get_async()
    response_text = response.responses

    if use_data_streaming:
        resources: List[Dict[str, Any]] = response.get_resources()
        assert len(resources) == 1
        assert resources[0]["id"] == "12355"
        assert resources[0]["resourceType"] == "Patient"
        assert response.chunk_number == 1
        assert response.response_headers is not None
        assert "Transfer-Encoding:chunked" in response.response_headers
    else:
        bundle = json.loads(response_text)
        assert "entry" in bundle, bundle
        responses_: List[Any] = [r["resource"] for r in bundle["entry"]]
        assert len(responses_) == 1
        assert responses_[0]["id"] == "12355"
        assert responses_[0]["resourceType"] == "Patient"
