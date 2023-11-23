import json
from typing import List

from mockserver_client.mockserver_client import (
    mock_request,
    mock_response,
    times,
    MockServerFriendlyClient,
)

from helix_fhir_client_sdk.fhir_client import FhirClient


def mock_calls_to_get_response(
    mock_client: MockServerFriendlyClient, relative_url: str
) -> None:
    """
    Function to mock common request to server which will be used when concurrent request and page size for retrieving
    ids are different.
    """
    # this is the first call made by the first concurrent request
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/PractitionerRole",
            method="GET",
            querystring={
                "_elements": "id",
                "_total": "accurate",
                "_count": "2",
                "_getpagesoffset": "0",
            },
        ),
        response=mock_response(
            body=json.dumps(
                [
                    {"resourceType": "PractitionerRole", "id": "111"},
                    {"resourceType": "PractitionerRole", "id": "112"},
                ]
            )
        ),
        timing=times(1),
    )

    # this is the first call made by the second concurrent request
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/PractitionerRole",
            method="GET",
            querystring={
                "_elements": "id",
                "_total": "accurate",
                "_count": "2",
                "_getpagesoffset": "1",
            },
        ),
        response=mock_response(
            body=json.dumps(
                [
                    {"resourceType": "PractitionerRole", "id": "113"},
                    {"resourceType": "PractitionerRole", "id": "114"},
                ]
            )
        ),
        timing=times(1),
    )


async def test_async_fhir_client_practitioner_role_for_diff_req() -> None:
    """
    Test case to check number of id's fetched for a resource are same when concurrent request and page size were
    different.We are making 2 calls here one with (concurrent_req=2,page_size_for_retrieving_ids=2) and another with
    (concurrent_req=3,page_size_for_retrieving_ids=2) and in both case we should get same number of id's
    """
    test_name = "test_async_fhir_client_practitioner_role_for_diff_req"
    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(
        base_url=mock_server_url
    )
    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    # this is the second call made by the first concurrent request
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/PractitionerRole",
            method="GET",
            querystring={
                "_elements": "id",
                "_total": "accurate",
                "_count": "2",
                "_getpagesoffset": "1",
                "id:above": "112",
            },
        ),
        response=mock_response(
            body=json.dumps([{"resourceType": "PractitionerRole", "id": "115"}])
        ),
        timing=times(1),
    )

    # this is the third call made by the first concurrent request
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/PractitionerRole",
            method="GET",
            querystring={
                "_elements": "id",
                "_total": "accurate",
                "_count": "2",
                "_getpagesoffset": "1",
                "id:above": "115",
            },
        ),
        response=mock_response(body=json.dumps([])),
        timing=times(1),
    )

    # this is the second call made by the second concurrent request
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/PractitionerRole",
            method="GET",
            querystring={
                "_elements": "id",
                "_total": "accurate",
                "_count": "2",
                "_getpagesoffset": "1",
                "id:above": "114",
            },
        ),
        response=mock_response(body=json.dumps([])),
        timing=times(1),
    )

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(absolute_url).resource("PractitionerRole")
    fhir_client = fhir_client.page_size(2)
    fhir_client = fhir_client.include_total(True)

    mock_calls_to_get_response(mock_client, relative_url)
    list_of_ids1: List[str] = await fhir_client.get_ids_for_query_async(
        concurrent_requests=2, page_size_for_retrieving_ids=2
    )

    mock_client.reset()
    # this is the second call made by the first concurrent request
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/PractitionerRole",
            method="GET",
            querystring={
                "_elements": "id",
                "_total": "accurate",
                "_count": "2",
                "_getpagesoffset": "2",
                "id:above": "112",
            },
        ),
        response=mock_response(body=json.dumps([])),
        timing=times(1),
    )

    # this is the second call made by the second concurrent request
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/PractitionerRole",
            method="GET",
            querystring={
                "_elements": "id",
                "_total": "accurate",
                "_count": "2",
                "_getpagesoffset": "2",
                "id:above": "114",
            },
        ),
        response=mock_response(body=json.dumps([])),
        timing=times(1),
    )

    # First call made by the third concurrent request
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/PractitionerRole",
            method="GET",
            querystring={
                "_elements": "id",
                "_total": "accurate",
                "_count": "2",
                "_getpagesoffset": "2",
            },
        ),
        response=mock_response(
            body=json.dumps([{"resourceType": "PractitionerRole", "id": "115"}])
        ),
        timing=times(1),
    )

    # this is the second call made by the third concurrent request
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/PractitionerRole",
            method="GET",
            querystring={
                "_elements": "id",
                "_total": "accurate",
                "_count": "2",
                "_getpagesoffset": "2",
                "id:above": "115",
            },
        ),
        response=mock_response(body=json.dumps([])),
        timing=times(1),
    )

    mock_calls_to_get_response(mock_client, relative_url)
    list_of_ids2: List[str] = await fhir_client.get_ids_for_query_async(
        concurrent_requests=3, page_size_for_retrieving_ids=2
    )

    # Assert len of ids are same when concurrent request and page size were different.
    assert len(list_of_ids1) == len(list_of_ids2)
