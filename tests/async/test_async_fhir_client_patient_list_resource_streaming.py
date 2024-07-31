import json
from typing import Optional, Any, Dict, List

from mockserver_client.mockserver_client import (
    mock_request,
    mock_response,
    times,
    MockServerFriendlyClient,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


async def test_fhir_client_patient_list_async_resource_streaming() -> None:
    print("")
    test_name = "test_fhir_client_patient_list_async"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(
        base_url=mock_server_url
    )

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    fhir: Dict[str, Any] = {
        "resourceType": "Bundle",
        "total": 2,
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "1"}},
            {"resource": {"resourceType": "Patient", "id": "2"}},
        ],
    }

    response_text: str = ""
    for e in fhir["entry"]:
        response_text += json.dumps(e) + "\n"
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

    resource_chunks: List[List[Dict[str, Any]]] = []

    async def on_resource(
        resources: Optional[List[Dict[str, Any]]], chunk_number: Optional[int] = None
    ) -> bool:
        print(f"Got chunk {chunk_number}: {resources}")
        if resources:
            resource_chunks.append(resources)
        return True

    response: FhirGetResponse = await fhir_client.get_async(
        resource_chunk_handler=on_resource
    )

    assert response.responses == ""

    assert len(resource_chunks) == 2
    assert resource_chunks[0] == [{"resource": {"id": "1", "resourceType": "Patient"}}]
    assert resource_chunks[1] == [{"resource": {"id": "2", "resourceType": "Patient"}}]
