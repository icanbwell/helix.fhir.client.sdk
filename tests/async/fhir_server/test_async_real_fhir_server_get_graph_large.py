import json
from os import environ
from typing import Any

import pytest
from compressedfhir.fhir.fhir_resource_list import FhirResourceList
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
    CompressedDictStorageType,
)
from objsize import get_deep_size

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse
from helix_fhir_client_sdk.utilities.fhir_helper import FhirHelper
from helix_fhir_client_sdk.utilities.fhir_server_helpers import FhirServerHelpers
from helix_fhir_client_sdk.utilities.practitioner_generator import PractitionerGenerator
from helix_fhir_client_sdk.utilities.size_calculator.size_calculator import (
    SizeCalculator,
)
from tests.logger_for_test import LoggerForTest


@pytest.mark.parametrize("use_data_streaming", [True, False])
@pytest.mark.parametrize("storage_type", ["raw", "compressed", "msgpack", "compressed_msgpack"])
async def test_async_real_fhir_server_get_graph_large(
    use_data_streaming: bool,
    storage_type: CompressedDictStorageType,
) -> None:
    environ["LOGLEVEL"] = "DEBUG"

    resource_type = "Practitioner"
    await FhirServerHelpers.clean_fhir_server_async(resource_type=resource_type)

    fhir_server_url: str = environ["FHIR_SERVER_URL"]
    auth_client_id = environ["FHIR_CLIENT_ID"]
    auth_client_secret = environ["FHIR_CLIENT_SECRET"]
    auth_well_known_url = environ["AUTH_CONFIGURATION_URI"]

    logger = LoggerForTest()

    fhir_client = FhirClient()
    fhir_client.logger(logger=logger)
    fhir_client = fhir_client.url(fhir_server_url).resource(resource_type)
    fhir_client = fhir_client.client_credentials(client_id=auth_client_id, client_secret=auth_client_secret)
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)

    count: int = 100
    roles_per_practitioner: int = 10

    id_dict: dict[str, list[str]] = PractitionerGenerator.get_ids(
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
    fhir_client = fhir_client.client_credentials(client_id=auth_client_id, client_secret=auth_client_secret)
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)

    bundle: dict[str, Any] = PractitionerGenerator.generate_resources_bundle(
        count=count, roles_per_practitioner=roles_per_practitioner
    )

    expected_resource_count = len(bundle["entry"])
    logger.info("expected_resource_count", expected_resource_count)

    merge_response: FhirMergeResponse | None = await FhirMergeResponse.from_async_generator(
        fhir_client.merge_async(json_data_list=[json.dumps(bundle)])
    )
    assert merge_response is not None
    logger.info(json.dumps(merge_response.responses))
    assert merge_response.status == 200, merge_response.responses
    assert len(merge_response.responses) == expected_resource_count, merge_response.responses
    # assert merge_response.responses[0]["created"] is True, merge_response.responses

    # Now start the test
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
    fhir_client = fhir_client.set_storage_mode(CompressedDictStorageMode(storage_type=storage_type))
    fhir_client = fhir_client.url(fhir_server_url).resource(resource_type)
    fhir_client = fhir_client.id_(id_dict[resource_type])
    fhir_client = fhir_client.action("$graph").action_payload(slot_practitioner_graph)
    fhir_client = fhir_client.additional_parameters(["contained=true"])
    fhir_client = fhir_client.client_credentials(client_id=auth_client_id, client_secret=auth_client_secret)
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)
    fhir_client = fhir_client.expand_fhir_bundle(False)
    fhir_client = fhir_client.limit(expected_resource_count)
    fhir_client = fhir_client.use_data_streaming(use_data_streaming)

    if use_data_streaming:
        responses: list[FhirGetResponse] = []
        response: FhirGetResponse | None = None
        resource_chunks: list[FhirResourceList] = []
        async for response1 in fhir_client.get_streaming_async():
            resources_in_chunk = response1.get_resources()
            assert isinstance(resources_in_chunk, FhirResourceList)
            logger.info(
                f"Chunk Number {response1.chunk_number} Received."
                f" Resource count=[{len(resources_in_chunk)}]: {response1.to_dict()}"
            )
            resource_chunks.append(resources_in_chunk)
            responses.append(response1)
            if not response:
                response = response1
            else:
                response = response.append(response1)

        assert response is not None
        resources: FhirResourceList = response.get_resources()
        assert isinstance(resources, FhirResourceList)

        assert response.response_headers is not None
        assert "Transfer-Encoding:chunked" in response.response_headers
        assert "Content-Encoding:gzip" in response.response_headers
        assert len(resources) == count
        # assert len(responses) == 4  # need new version of fhir server that fixes streaming from graph
        assert resources[0]["id"].startswith("practitioner-")
        assert resources[0]["resourceType"] == resource_type
        assert response.chunk_number is not None

        logger.info(f"====== Response with {storage_type=} {use_data_streaming=} ======")
        logger.info(
            f"{response.get_resource_count()} resources, {SizeCalculator.locale_format_bytes(get_deep_size(response))}"
        )
        logger.info(f"====== End Response with {storage_type=} ======")
        # assert response.chunk_number >= 5
    else:
        response = await fhir_client.get_async()
        assert response.response_headers is not None
        assert "Content-Encoding:gzip" in response.response_headers
        response_text = response.get_response_text()
        bundle = json.loads(response_text)
        assert "entry" in bundle, bundle
        responses_: list[Any] = [r["resource"] for r in bundle["entry"]]
        assert len(responses_) == count
        assert responses_[0]["id"].startswith("practitioner-")
        assert responses_[0]["resourceType"] == resource_type

        logger.info(f"====== Response with {storage_type=} {use_data_streaming=} ======")
        logger.info(
            f"{response.get_resource_count()} resources, {SizeCalculator.locale_format_bytes(get_deep_size(response))}"
        )
        logger.info(f"====== End Response with {storage_type=} ======")
