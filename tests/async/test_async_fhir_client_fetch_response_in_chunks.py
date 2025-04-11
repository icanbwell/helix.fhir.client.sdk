import json
from typing import AsyncGenerator, Optional, Tuple, Dict, List, cast

from aiohttp import StreamReader
from mockserver_client.mockserver_client import (
    mock_request,
    mock_response,
    times,
    MockServerFriendlyClient,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from unittest.mock import AsyncMock, patch

from helix_fhir_client_sdk.utilities.retryable_aiohttp_response import (
    RetryableAioHttpResponse,
)


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

    class MyRetryableAioHttpResponse(RetryableAioHttpResponse):
        """
        Mocked ClientResponse class of aiohttp module.
        """

        def __init__(
            self,
            status: int,
            response_headers: Dict[str, str],
            content: List[Tuple[bytes, bool]],
        ) -> None:
            super().__init__(
                ok=status < 400,
                status=status,
                response_headers=response_headers,
                content=cast(StreamReader, ContentIterator(content)),
                response_text=response_text,
                use_data_streaming=True,
                results_by_url=[],
                access_token=None,
                access_token_expiry_date=None,
                retry_count=0,
            )

    class ContentIterator:
        """
        Mocked stream reader class of aiohttp module. This class was mocked to mock the behaviour of iter_chunks method.
        """

        def __init__(self, content: List[Tuple[bytes, bool]]) -> None:
            self._content = content

        async def iter_chunks(self) -> AsyncGenerator[Tuple[bytes, bool], None]:
            for content in self._content:
                yield content

        async def iter_chunked(self, chunk_size: int) -> AsyncGenerator[bytes, None]:
            for content, chunk_number in self._content:
                yield content

        # noinspection PyMethodMayBeStatic
        def at_eof(self) -> bool:
            return False

    # Mocking send_fhir_request_async method of fhir client class
    with patch.object(
        fhir_client, "_send_fhir_request_async", new_callable=AsyncMock
    ) as mock_send_fhir_request_async:
        mocked_response = MyRetryableAioHttpResponse(
            status=200,
            response_headers={"Accept": "application/fhir+ndjson"},
            content=[
                (b'{"resourceType": "Patient", "id": "12355"', False),
                (b', "first_name": "test"}', True),
            ],
        )
        mock_send_fhir_request_async.return_value = mocked_response
        response: FhirGetResponse = await fhir_client.get_async(
            data_chunk_handler=on_chunk
        )

    print(response.get_response_text())
    assert response.get_response_text() == response_text
