import json
from typing import Any, Dict, List

from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient


async def test_get_resources_by_query_async_with_additional_params() -> None:
    # Arrange
    test_name = "test_get_resources_by_query_async_with_additional_params"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(
        base_url=mock_server_url
    )

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*")
    mock_client.reset()

    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Location",
            method="GET",
            querystring={
                "_elements": "id",
                "_count": "10000",
                "_getpagesoffset": "0",
                "identifier": "http://thedacare.org/epic|222126",
            },
        ),
        response=mock_response(
            body=json.dumps(
                {
                    "resourceType": "Bundle",
                    "total": 0,
                    "entry": [
                        {
                            "resource": {
                                "resourceType": "Location",
                                "id": "tc-epic-222126",
                            }
                        }
                    ],
                }
            )
        ),
        timing=times(1),
    )

    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Location",
            method="GET",
            querystring={
                "_elements": "id",
                "_count": "10000",
                "_getpagesoffset": "1",
                "identifier": "http://thedacare.org/epic|222126",
            },
        ),
        response=mock_response(
            body=json.dumps(
                {
                    "resourceType": "Bundle",
                    "total": 0,
                    "entry": [],
                }
            )
        ),
        timing=times(1),
    )

    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Location",
            method="GET",
            querystring={
                "_elements": "id",
                "_count": "10000",
                "_getpagesoffset": "2",
                "identifier": "http://thedacare.org/epic|222126",
            },
        ),
        response=mock_response(
            body=json.dumps(
                {
                    "resourceType": "Bundle",
                    "total": 0,
                    "entry": [],
                }
            )
        ),
        timing=times(1),
    )

    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Location",
            method="GET",
            querystring={
                "_elements": "id",
                "_count": "10000",
                "_getpagesoffset": "3",
                "identifier": "http://thedacare.org/epic|222126",
            },
        ),
        response=mock_response(
            body=json.dumps(
                {
                    "resourceType": "Bundle",
                    "total": 0,
                    "entry": [],
                }
            )
        ),
        timing=times(1),
    )

    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Location",
            method="GET",
            querystring={
                "_elements": "id",
                "_count": "10000",
                "_getpagesoffset": "4",
                "identifier": "http://thedacare.org/epic|222126",
            },
        ),
        response=mock_response(
            body=json.dumps(
                {
                    "resourceType": "Bundle",
                    "total": 0,
                    "entry": [],
                }
            )
        ),
        timing=times(1),
    )

    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Location",
            method="GET",
            querystring={
                "_elements": "id",
                "_count": "10000",
                "_getpagesoffset": "5",
                "identifier": "http://thedacare.org/epic|222126",
            },
        ),
        response=mock_response(
            body=json.dumps(
                {
                    "resourceType": "Bundle",
                    "total": 0,
                    "entry": [],
                }
            )
        ),
        timing=times(1),
    )

    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Location",
            method="GET",
            querystring={
                "_elements": "id",
                "_count": "10000",
                "_getpagesoffset": "6",
                "identifier": "http://thedacare.org/epic|222126",
            },
        ),
        response=mock_response(
            body=json.dumps(
                {
                    "resourceType": "Bundle",
                    "total": 0,
                    "entry": [],
                }
            )
        ),
        timing=times(1),
    )

    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Location",
            method="GET",
            querystring={
                "_elements": "id",
                "_count": "10000",
                "_getpagesoffset": "7",
                "identifier": "http://thedacare.org/epic|222126",
            },
        ),
        response=mock_response(
            body=json.dumps(
                {
                    "resourceType": "Bundle",
                    "total": 0,
                    "entry": [],
                }
            )
        ),
        timing=times(1),
    )

    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Location",
            method="GET",
            querystring={
                "_elements": "id",
                "_count": "10000",
                "_getpagesoffset": "8",
                "identifier": "http://thedacare.org/epic|222126",
            },
        ),
        response=mock_response(
            body=json.dumps(
                {
                    "resourceType": "Bundle",
                    "total": 0,
                    "entry": [],
                }
            )
        ),
        timing=times(1),
    )

    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Location",
            method="GET",
            querystring={
                "_elements": "id",
                "_count": "10000",
                "_getpagesoffset": "9",
                "identifier": "http://thedacare.org/epic|222126",
            },
        ),
        response=mock_response(
            body=json.dumps(
                {
                    "resourceType": "Bundle",
                    "total": 0,
                    "entry": [],
                }
            )
        ),
        timing=times(1),
    )

    # now mock the actual calls to get resources
    response_text: Dict[str, Any] = {"resourceType": "Location", "id": "tc-epic-222126"}
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Location/tc-epic-222126",
            method="GET",
            querystring={
                "_count": "10000",
                "_getpagesoffset": "0",
                "identifier": "http://thedacare.org/epic|222126",
            },
        ),
        response=mock_response(body=json.dumps(response_text)),
        timing=times(1),
    )

    # Act
    fhir_client = FhirClient()
    fhir_client = (
        fhir_client.url(absolute_url)
        .resource("Location")
        .additional_parameters(["identifier=http://thedacare.org/epic|222126"])
    )
    response: List[Dict[str, Any]] = await fhir_client.get_resources_by_query_async()

    # Assert
    assert response == [response_text]
