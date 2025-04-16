import json
from logging import Logger
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
from tests.logger_for_test import LoggerForTest


async def test_fhir_client_patient_list_async_resource_streaming() -> None:
    logger: Logger = LoggerForTest()
    test_name = "test_fhir_client_patient_list_async"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(base_url=mock_server_url)

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    fhir: dict[str, Any] = {
        "resourceType": "Bundle",
        "total": 2,
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "1"}},
            {"resource": {"resourceType": "Patient", "id": "2"}},
        ],
    }

    response_text: str = ""
    for e in fhir["entry"]:
        response_text += json.dumps(e["resource"]) + "\n"
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Patient",
            method="GET",
            headers={"Accept": "application/fhir+ndjson"},
        ),
        response=mock_response(body=response_text),
        timing=times(2),
    )

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(absolute_url).resource("Patient")
    fhir_client = fhir_client.use_data_streaming(True)
    fhir_client = fhir_client.chunk_size(10)

    resource_chunks: list[FhirResourceList] = []

    response: FhirGetResponse | None = None
    async for response1 in fhir_client.get_streaming_async():
        logger.info(f"Got response from chunk {response1.chunk_number}: {response1.to_dict()}")
        resources = response1.get_resources()
        assert isinstance(resources, FhirResourceList)
        resource_chunks.append(resources)
        if not response:
            response = response1
        else:
            response = response.append(response1)

    assert response
    # assert response.responses == ""

    assert len(resource_chunks) == 2
    assert [r.dict() for r in resource_chunks[0]] == [{"id": "1", "resourceType": "Patient"}]
    assert [r.dict() for r in resource_chunks[1]] == [{"id": "2", "resourceType": "Patient"}]
