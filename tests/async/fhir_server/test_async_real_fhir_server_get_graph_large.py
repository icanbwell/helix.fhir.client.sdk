import json
from os import environ
from typing import Any, List, Dict, Optional

import pytest

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse
from helix_fhir_client_sdk.utilities.fhir_server_helpers import FhirServerHelpers
from helix_fhir_client_sdk.utilities.practitioner_generator import PractitionerGenerator
from tests.test_logger import TestLogger


@pytest.mark.parametrize("use_data_streaming", [True, False])
async def test_async_real_fhir_server_get_graph_large(
    use_data_streaming: bool,
) -> None:
    await FhirServerHelpers.clean_fhir_server_async(resource_type="Patient")

    environ["LOGLEVEL"] = "DEBUG"

    fhir_server_url: str = environ["FHIR_SERVER_URL"]
    auth_client_id = environ["FHIR_CLIENT_ID"]
    auth_client_secret = environ["FHIR_CLIENT_SECRET"]
    auth_well_known_url = environ["AUTH_CONFIGURATION_URI"]

    logger = TestLogger()

    fhir_client = FhirClient()
    fhir_client.logger(logger=logger)
    fhir_client = fhir_client.url(fhir_server_url).resource("Practitioner")
    fhir_client = fhir_client.client_credentials(
        client_id=auth_client_id, client_secret=auth_client_secret
    )
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)

    count: int = 50

    id_dict: Dict[str, List[str]] = PractitionerGenerator.get_ids(count)
    print(f"Deleting {count} Practitioner resources: {id_dict['Practitioner']}")
    for i in id_dict["Practitioner"]:
        resource_id = f"{i}"
        delete_response = (
            await fhir_client.resource("Practitioner").id_(resource_id).delete_async()
        )
        assert delete_response.status == 204, delete_response.responses
    print(f"Deleted {count} Practitioner resources")
    print(f"Deleting {count} Organization resource {id_dict['Organization']}")
    for i in id_dict["Organization"]:
        resource_id = f"{i}"
        delete_response = (
            await fhir_client.resource("Organization").id_(resource_id).delete_async()
        )
        assert delete_response.status == 204, delete_response.responses
    print(f"Deleted {count} Organization resources")
    print(f"Deleting {count} PractitionerRole resources {id_dict['PractitionerRole']}")
    for i in id_dict["PractitionerRole"]:
        resource_id = f"{i}"
        delete_response = (
            await fhir_client.resource("PractitionerRole")
            .id_(resource_id)
            .delete_async()
        )
        assert delete_response.status == 204, delete_response.responses
    print(f"Deleted {count} PractitionerRole resources")

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(fhir_server_url).resource("Practitioner")
    fhir_client = fhir_client.client_credentials(
        client_id=auth_client_id, client_secret=auth_client_secret
    )
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)

    bundle: Dict[str, Any] = PractitionerGenerator.generate_resources_bundle(count)

    expected_resource_count = len(bundle["entry"])

    merge_response: FhirMergeResponse = await FhirMergeResponse.from_async_generator(
        fhir_client.merge_async(json_data_list=[json.dumps(bundle)])
    )
    print(json.dumps(merge_response.responses))
    assert merge_response.status == 200, merge_response.responses
    assert (
        len(merge_response.responses) == expected_resource_count
    ), merge_response.responses
    # assert merge_response.responses[0]["created"] is True, merge_response.responses

    slot_practitioner_graph = {
        "resourceType": "GraphDefinition",
        "id": "o",
        "name": "provider_slots",
        "status": "active",
        "start": "Practitioner",
        "link": [
            {
                "target": [
                    {
                        "type": "PractitionerRole",
                        "params": "practitioner={ref}",
                        "link": [
                            {
                                "path": "organization",
                                "target": [
                                    {
                                        "type": "Organization",
                                        "link": [
                                            {
                                                "path": "endpoint[x]",
                                                "target": [{"type": "Endpoint"}],
                                            }
                                        ],
                                    }
                                ],
                            },
                            {
                                "target": [
                                    {
                                        "type": "Schedule",
                                        "params": "actor={ref}",
                                        "link": [
                                            {
                                                "target": [
                                                    {
                                                        "type": "Slot",
                                                        "params": "schedule={ref}",
                                                    }
                                                ]
                                            }
                                        ],
                                    }
                                ]
                            },
                        ],
                    }
                ]
            }
        ],
    }

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(fhir_server_url).resource("Practitioner")
    fhir_client = fhir_client.id_(id_dict["Practitioner"])
    fhir_client = fhir_client.action("$graph").action_payload(slot_practitioner_graph)
    fhir_client = fhir_client.client_credentials(
        client_id=auth_client_id, client_secret=auth_client_secret
    )
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)
    fhir_client = fhir_client.expand_fhir_bundle(False)
    fhir_client = fhir_client.limit(1000)
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
        resources: List[Dict[str, Any]] = response.get_resources()
        assert response.response_headers is not None
        assert "Transfer-Encoding:chunked" in response.response_headers
        assert "Content-Encoding:gzip" in response.response_headers
        assert len(resources) == expected_resource_count
        assert len(responses) > 1
        assert resources[0]["id"].startswith("example-")
        assert resources[0]["resourceType"] == "Practitioner"
        assert response.chunk_number == 7
    else:
        response = await fhir_client.get_async()
        assert response.response_headers is not None
        assert "Content-Encoding:gzip" in response.response_headers
        response_text = response.responses
        bundle = json.loads(response_text)
        assert "entry" in bundle, bundle
        responses_: List[Any] = [r["resource"] for r in bundle["entry"]]
        assert len(responses_) == 1000
        assert responses_[0]["id"].startswith("example-")
        assert responses_[0]["resourceType"] == "Practitioner"
