import json
from os import environ
from typing import Any, List, Dict, Optional

import pytest

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse
from helix_fhir_client_sdk.utilities.fhir_helper import FhirHelper
from helix_fhir_client_sdk.utilities.fhir_server_helpers import FhirServerHelpers
from helix_fhir_client_sdk.utilities.practitioner_generator import PractitionerGenerator
from tests.test_logger import TestLogger


@pytest.mark.parametrize("use_data_streaming", [True, False])
async def test_async_real_fhir_server_get_graph_large(
    use_data_streaming: bool,
) -> None:
    environ["LOGLEVEL"] = "DEBUG"

    resource_type = "Practitioner"
    await FhirServerHelpers.clean_fhir_server_async(resource_type=resource_type)

    fhir_server_url: str = environ["FHIR_SERVER_URL"]
    auth_client_id = environ["FHIR_CLIENT_ID"]
    auth_client_secret = environ["FHIR_CLIENT_SECRET"]
    auth_well_known_url = environ["AUTH_CONFIGURATION_URI"]

    logger = TestLogger()

    fhir_client = FhirClient()
    fhir_client.logger(logger=logger)
    fhir_client = fhir_client.url(fhir_server_url).resource(resource_type)
    fhir_client = fhir_client.client_credentials(
        client_id=auth_client_id, client_secret=auth_client_secret
    )
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)

    count: int = 100
    roles_per_practitioner: int = 10

    id_dict: Dict[str, List[str]] = PractitionerGenerator.get_ids(
        count=count, roles_per_practitioner=roles_per_practitioner
    )
    # delete Practitioner resources
    await FhirHelper.delete_resources_by_ids_async(
        fhir_client=fhir_client,
        resource_type=resource_type,
        id_list=id_dict[resource_type],
    )
    # delete Organization resources
    await FhirHelper.delete_resources_by_ids_async(
        fhir_client=fhir_client,
        resource_type="Organization",
        id_list=id_dict["Organization"],
    )
    # delete PractitionerRole resources
    await FhirHelper.delete_resources_by_ids_async(
        fhir_client=fhir_client,
        resource_type="PractitionerRole",
        id_list=id_dict["PractitionerRole"],
    )

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(fhir_server_url).resource(resource_type)
    fhir_client = fhir_client.client_credentials(
        client_id=auth_client_id, client_secret=auth_client_secret
    )
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)

    bundle: Dict[str, Any] = PractitionerGenerator.generate_resources_bundle(
        count=count, roles_per_practitioner=roles_per_practitioner
    )

    expected_resource_count = len(bundle["entry"])
    print("expected_resource_count", expected_resource_count)

    merge_response: Optional[FhirMergeResponse] = (
        await FhirMergeResponse.from_async_generator(
            fhir_client.merge_async(json_data_list=[json.dumps(bundle)])
        )
    )
    assert merge_response is not None
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
        "start": resource_type,
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
    fhir_client = fhir_client.url(fhir_server_url).resource(resource_type)
    fhir_client = fhir_client.id_(id_dict[resource_type])
    fhir_client = fhir_client.action("$graph").action_payload(slot_practitioner_graph)
    fhir_client = fhir_client.additional_parameters(["contained=true"])
    fhir_client = fhir_client.client_credentials(
        client_id=auth_client_id, client_secret=auth_client_secret
    )
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)
    fhir_client = fhir_client.expand_fhir_bundle(False)
    fhir_client = fhir_client.limit(expected_resource_count)
    fhir_client = fhir_client.use_data_streaming(use_data_streaming)

    if use_data_streaming:
        responses: List[FhirGetResponse] = []
        response: Optional[FhirGetResponse] = None
        resource_chunks: List[List[Dict[str, Any]]] = []
        async for response1 in fhir_client.get_streaming_async():
            resources_in_chunk = response1.get_resources()
            print(
                f"Chunk Number {response1.chunk_number} Received."
                f" Resource count=[{len(resources_in_chunk)}]: {response1}"
            )
            resource_chunks.append(resources_in_chunk)
            responses.append(response1)
            if not response:
                response = response1
            else:
                response.append(response1)

        assert response is not None
        resources: List[Dict[str, Any]] = response.get_resources()
        assert response.response_headers is not None
        assert "Transfer-Encoding:chunked" in response.response_headers
        assert "Content-Encoding:gzip" in response.response_headers
        assert len(resources) == count
        # assert len(responses) == 4  # need new version of fhir server that fixes streaming from graph
        assert resources[0]["id"].startswith("practitioner-")
        assert resources[0]["resourceType"] == resource_type
        assert response.chunk_number is not None
        # assert response.chunk_number >= 5
    else:
        response = await fhir_client.get_async()
        assert response.response_headers is not None
        assert "Content-Encoding:gzip" in response.response_headers
        response_text = response.responses
        bundle = json.loads(response_text)
        assert "entry" in bundle, bundle
        responses_: List[Any] = [r["resource"] for r in bundle["entry"]]
        assert len(responses_) == count
        assert responses_[0]["id"].startswith("practitioner-")
        assert responses_[0]["resourceType"] == resource_type
