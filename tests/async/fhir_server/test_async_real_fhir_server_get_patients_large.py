import json
from os import environ
from typing import Any, List, Dict, Optional

import pytest

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse
from helix_fhir_client_sdk.utilities.fhir_helper import FhirHelper
from helix_fhir_client_sdk.utilities.fhir_server_helpers import FhirServerHelpers


@pytest.mark.parametrize("use_data_streaming", [True, False])
async def test_async_real_fhir_server_get_patients_large(
    use_data_streaming: bool,
) -> None:
    print()
    resource_type = "Patient"
    await FhirServerHelpers.clean_fhir_server_async(resource_type=resource_type)

    environ["LOGLEVEL"] = "DEBUG"

    fhir_server_url: str = environ["FHIR_SERVER_URL"]
    auth_client_id = environ["FHIR_CLIENT_ID"]
    auth_client_secret = environ["FHIR_CLIENT_SECRET"]
    auth_well_known_url = environ["AUTH_CONFIGURATION_URI"]

    count = 1000

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(fhir_server_url).resource(resource_type)
    fhir_client = fhir_client.client_credentials(
        client_id=auth_client_id, client_secret=auth_client_secret
    )
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)

    resource = await FhirHelper.create_test_patients(count)
    merge_response: FhirMergeResponse = await FhirMergeResponse.from_async_generator(
        fhir_client.merge_async(json_data_list=[json.dumps(resource)])
    )
    print(merge_response.responses)
    assert merge_response.status == 200, merge_response.responses
    assert len(merge_response.responses) == count, merge_response.responses
    assert merge_response.responses[0]["created"] is True, merge_response.responses

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(fhir_server_url).resource(resource_type)
    fhir_client = fhir_client.client_credentials(
        client_id=auth_client_id, client_secret=auth_client_secret
    )
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)
    fhir_client = fhir_client.expand_fhir_bundle(False)
    fhir_client = fhir_client.limit(count)
    fhir_client = fhir_client.use_data_streaming(use_data_streaming)

    if use_data_streaming:
        responses: List[FhirGetResponse] = []
        response: Optional[FhirGetResponse] = None
        resource_chunks: List[List[Dict[str, Any]]] = []
        async for response1 in fhir_client.get_streaming_async():
            resources_in_chunk = response1.get_resources()
            print(
                f"Chunk Received {response1.chunk_number} [{len(resources_in_chunk)}]: {response1}"
            )
            resource_chunks.append(resources_in_chunk)
            responses.append(response1)
            if not response:
                response = response1
            else:
                response.append([response1])

        assert response is not None
        assert response.response_headers is not None
        assert "Transfer-Encoding:chunked" in response.response_headers
        assert "Content-Encoding:gzip" in response.response_headers
        resources: List[Dict[str, Any]] = response.get_resources()
        assert len(resources) == count
        print("Number of chunks received:", len(responses))
        assert len(responses) > 1
        assert resources[0]["id"].startswith("example-")
        assert resources[0]["resourceType"] == resource_type
        assert response.chunk_number == 7
    else:
        response = await fhir_client.get_async()
        assert response.response_headers is not None
        assert "Content-Encoding:gzip" in response.response_headers
        response_text = response.responses
        bundle = json.loads(response_text)
        assert "entry" in bundle, bundle
        responses_: List[Any] = [r["resource"] for r in bundle["entry"]]
        assert len(responses_) == count
        assert responses_[0]["id"].startswith("example-")
        assert responses_[0]["resourceType"] == resource_type
