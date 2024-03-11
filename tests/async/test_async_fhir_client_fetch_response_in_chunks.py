import json
from typing import AsyncGenerator, Optional, Any, Tuple, Dict, List

from mockserver_client.mockserver_client import (
    mock_request,
    mock_response,
    times,
    MockServerFriendlyClient,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from unittest.mock import AsyncMock, patch


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

    response_text: str = json.dumps(
        {"resourceType": "Patient", "id": "12355", "first_name": "test"}
    )
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

    async def on_chunk(line: bytes, chunk_number: Optional[int] = None) -> bool:
        print(f"Got chunk {chunk_number}: {line.decode('utf-8')}")
        return True

    class ClientResponse:
        """
        Mocked ClientResponse class of aiohttp module.
        """

        def __init__(
            self,
            status: int,
            headers: Dict[str, str],
            content: List[Tuple[bytes, bool]],
        ) -> None:
            self.status = status
            self._headers = headers
            self._content = content

        @property
        def content(self) -> Any:
            return ContentIterator(self._content)

        @property
        def headers(self) -> Any:
            return GetHeader(self._headers)

    class ContentIterator:
        """
        Mocked stream reader class of aiohttp module. This class was mocked to mock the behaviour of iter_chunks method.
        """

        def __init__(self, content: List[Tuple[bytes, bool]]) -> None:
            self._content = content

        async def iter_chunks(self) -> AsyncGenerator[Tuple[bytes, bool], None]:
            for content in self._content:
                yield content

    class GetHeader(dict[str, Any]):
        """
        Mocked CIMultiDictProxy class of multidict module. This class was mocked to mock the behaviour of getone method.
        """

        def __init__(self, header: Dict[str, str]) -> None:
            super().__init__()
            self._header = header

        def getone(self, key: str, *args: Any, **kwargs: Any) -> Any:
            return self._header.get(key, None)

    # Mocking send_fhir_request_async method of fhir client class
    with patch.object(
        fhir_client, "_send_fhir_request_async", new_callable=AsyncMock
    ) as mock_send_fhir_request_async:
        mocked_response = ClientResponse(
            200,
            {"Accept": "application/fhir+ndjson"},
            [
                (b'{"resourceType": "Patient", "id": "12355"', False),
                (b', "first_name": "test"}', True),
            ],
        )
        mock_send_fhir_request_async.return_value = mocked_response
        response: FhirGetResponse = await fhir_client.get_async(
            data_chunk_handler=on_chunk
        )

    print(response.responses)
    assert response.responses == response_text
