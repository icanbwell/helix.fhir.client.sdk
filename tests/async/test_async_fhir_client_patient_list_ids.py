import datetime
import json
from os import environ
from typing import List

from mockserver_client.mockserver_client import (
    mock_request,
    mock_response,
    times,
    MockServerFriendlyClient,
)

from helix_fhir_client_sdk.fhir_client import FhirClient


async def test_fhir_client_patient_list_ids_async() -> None:
    test_name = "test_fhir_client_patient_list_ids_async"

    environ["LOGLEVEL"] = "DEBUG"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(
        base_url=mock_server_url
    )

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    last_updated_after = datetime.datetime.strptime("2022-01-10", "%Y-%m-%d")

    response_text: str = json.dumps(
        [
            {"resourceType": "Patient", "id": "12355"},
            {"resourceType": "Patient", "id": "5555"},
        ]
    )
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Patient",
            method="GET",
            querystring={
                "_elements": "id",
                "_count": "10000",
                "_getpagesoffset": "0",
                "_lastUpdated": "ge2022-01-10T00:00:00Z",
            },
        ),
        response=mock_response(body=response_text),
        timing=times(1),
    )

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(absolute_url).resource("Patient")
    fhir_client = fhir_client.last_updated_after(last_updated_after)
    list_of_ids: List[str] = [s async for s in fhir_client.get_ids_for_query_async()]

    print(json.dumps(list_of_ids))
    assert list_of_ids == ["12355", "5555"]
