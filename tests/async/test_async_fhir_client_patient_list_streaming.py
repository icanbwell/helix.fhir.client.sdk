import json
from logging import Logger
from os import environ
from typing import Any

from compressedfhir.fhir.fhir_resource_list import FhirResourceList
from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.utilities.fhir_helper import FhirHelper
from tests.logger_for_test import LoggerForTest


async def test_fhir_client_patient_list_async_streaming() -> None:
    logger: Logger = LoggerForTest()
    test_name = "test_fhir_client_patient_list_async"

    environ["LOGLEVEL"] = "DEBUG"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(base_url=mock_server_url)

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    fhir: dict[str, Any] = await FhirHelper.create_test_patients(100)

    response_text: str = ""
    for e in fhir["entry"]:
        response_text += json.dumps(e["resource"]) + "\n"

    # noinspection PyArgumentList
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Patient",
            method="GET",
            headers={"Accept": "application/fhir+ndjson"},
        ),
        response=mock_response(
            body=response_text,
            headers={"Content-Type": "application/fhir+ndjson"},
            connectionOptions={"chunkSize": 10},
        ),
        timing=times(2),
    )

    fhir_client = FhirClient()
    fhir_client.logger(logger=logger)
    fhir_client = fhir_client.url(absolute_url).resource("Patient")
    fhir_client = fhir_client.use_data_streaming(True)
    fhir_client = fhir_client.chunk_size(10)

    responses: list[FhirGetResponse] = []
    response: FhirGetResponse | None = None
    resource_chunks: list[FhirResourceList] = []
    async for response1 in fhir_client.get_streaming_async():
        resources_in_chunk = response1.get_resources()
        assert isinstance(resources_in_chunk, FhirResourceList)
        logger.info(f"Chunk {response1.chunk_number} [{len(resources_in_chunk)}]: {response1.to_dict()}")

        resource_chunks.append(resources_in_chunk)
        if not response:
            response = response1
        else:
            response = response.append(response1)
        responses.append(response1)

    assert response is not None

    resources: FhirResourceList = response.get_resources()
    assert isinstance(resources, FhirResourceList)

    mock_client.verify_expectations()

    assert len(resources) == 100

    assert len(responses) > 1
    assert resources[0]["id"].startswith("example-")
    assert resources[0]["resourceType"] == "Patient"
