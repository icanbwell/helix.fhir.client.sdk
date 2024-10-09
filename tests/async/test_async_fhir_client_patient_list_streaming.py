import json
from typing import Optional

from mockserver_client.mockserver_client import (
    mock_request,
    mock_response,
    times,
    MockServerFriendlyClient,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


async def test_fhir_client_patient_list_async_streaming() -> None:
    test_name = "test_fhir_client_patient_list_async"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(
        base_url=mock_server_url
    )

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    response_text: str = json.dumps({"resourceType": "Patient", "id": "12355"})
    mock_client.expect(
        mock_request(
            path=f"/{relative_url}/Patient",
            method="GET",
            headers={"Accept": "application/fhir+ndjson"},
            querystring={"_getpagesoffset": "3"},
        ),
        mock_response(body=response_text),
        timing=times(2),
    )

    fhir_client = FhirClient()
    fhir_client = (
        fhir_client.url(absolute_url)
        .resource("Patient")
        .page_number(3)
        .use_data_streaming(True)
    )

    async def on_chunk(data: bytes, chunk_number: Optional[int]) -> bool:
        print(f"Got chunk {chunk_number}: {data.decode('utf-8')}")
        return True

    response: FhirGetResponse = await fhir_client.get_async(data_chunk_handler=on_chunk)

    print(response.responses)
    assert response.responses == response_text
    # test page_number can se set independent of page_size param
    assert response.url == f"{absolute_url}/Patient?_getpagesoffset=3"

    # test page_size can se set independent of page_number
    mock_client.expect(
        mock_request(
            path=f"/{relative_url}/Patient",
            method="GET",
            headers={"Accept": "application/fhir+ndjson"},
            querystring={"_count": "2"},
        ),
        mock_response(body=response_text),
        timing=times(2),
    )
    fhir_client._page_size = None
    fhir_client._page_number = None
    fhir_client = (
        fhir_client.url(absolute_url)
        .resource("Patient")
        .page_size(2)
        .use_data_streaming(True)
    )
    fhir_response: FhirGetResponse = await fhir_client.get_async(
        data_chunk_handler=on_chunk
    )
    assert fhir_response.url == f"{absolute_url}/Patient?_count=2"
