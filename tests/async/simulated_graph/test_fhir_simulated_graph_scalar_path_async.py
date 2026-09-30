import json
from pathlib import Path
from typing import Any

from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


async def test_fhir_simulated_graph_scalar_path_async() -> None:
    """
    A `path` link whose final segment resolves to a single (0..1) value must still be
    followed.  `Media.content` is a 0..1 Attachment, so `content[x].url` yields the bare
    string "Binary/2" rather than a list of references -- the `[x]` marker is a no-op on a
    non-repeating element.  The Binary still has to be fetched.
    """
    data_dir: Path = Path(__file__).parent.joinpath("./")
    with open(data_dir.joinpath("graphs").joinpath("media_binary.json")) as file:
        graph_json: dict[str, Any] = json.loads(file.read())

    test_name = test_fhir_simulated_graph_scalar_path_async.__name__

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(base_url=mock_server_url)

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    mock_client.expect(
        request=mock_request(path=f"/{relative_url}/Media/1", method="GET"),
        response=mock_response(
            body={
                "resourceType": "Media",
                "id": "1",
                "status": "completed",
                "content": {"contentType": "image/jpeg", "url": "Binary/2"},
            }
        ),
        timing=times(1),
    )

    mock_client.expect(
        request=mock_request(path=f"/{relative_url}/Binary/2", method="GET"),
        response=mock_response(body={"resourceType": "Binary", "id": "2", "contentType": "image/jpeg"}),
        timing=times(1),
    )

    fhir_client = FhirClient()
    fhir_client = fhir_client.expand_fhir_bundle(False)
    fhir_client = fhir_client.set_access_token("my_access_token")
    fhir_client = fhir_client.url(absolute_url).resource("Media")

    response: FhirGetResponse | None = await FhirGetResponse.from_async_generator(
        fhir_client.simulate_graph_streaming_async(
            id_="1",
            graph_json=graph_json,
            contained=False,
            separate_bundle_resources=False,
        )
    )
    assert response is not None

    bundle: dict[str, Any] = json.loads(response.get_response_text())
    resource_ids: list[str] = sorted(
        f"{e['resource']['resourceType']}/{e['resource']['id']}"
        for e in bundle["entry"]
        if e["resource"]["resourceType"] != "OperationOutcome"
    )

    assert resource_ids == ["Binary/2", "Media/1"]


async def test_fhir_simulated_graph_scalar_path_reference_dict_async() -> None:
    """
    Same no-op `[x]`, but the 0..1 element is a Reference rather than a url string.
    Without normalising, the loop iterates the Attachment/Reference dict's *keys*
    ("reference"), which never resolves.
    """
    graph_json: dict[str, Any] = {
        "resourceType": "GraphDefinition",
        "id": "singleton_reference",
        "name": "singleton_reference",
        "status": "active",
        "start": "MedicationRequest",
        "link": [
            {
                "path": "dispenseRequest[x].performer",
                "target": [{"type": "Organization"}],
            }
        ],
    }

    test_name = test_fhir_simulated_graph_scalar_path_reference_dict_async.__name__

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(base_url=mock_server_url)

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    mock_client.expect(
        request=mock_request(path=f"/{relative_url}/MedicationRequest/1", method="GET"),
        response=mock_response(
            body={
                "resourceType": "MedicationRequest",
                "id": "1",
                "status": "active",
                "intent": "order",
                "dispenseRequest": {"performer": {"reference": "Organization/3"}},
            }
        ),
        timing=times(1),
    )

    mock_client.expect(
        request=mock_request(path=f"/{relative_url}/Organization/3", method="GET"),
        response=mock_response(body={"resourceType": "Organization", "id": "3"}),
        timing=times(1),
    )

    fhir_client = FhirClient()
    fhir_client = fhir_client.expand_fhir_bundle(False)
    fhir_client = fhir_client.set_access_token("my_access_token")
    fhir_client = fhir_client.url(absolute_url).resource("MedicationRequest")

    response: FhirGetResponse | None = await FhirGetResponse.from_async_generator(
        fhir_client.simulate_graph_streaming_async(
            id_="1",
            graph_json=graph_json,
            contained=False,
            separate_bundle_resources=False,
        )
    )
    assert response is not None

    bundle: dict[str, Any] = json.loads(response.get_response_text())
    resource_ids: list[str] = sorted(
        f"{e['resource']['resourceType']}/{e['resource']['id']}"
        for e in bundle["entry"]
        if e["resource"]["resourceType"] != "OperationOutcome"
    )

    assert resource_ids == ["MedicationRequest/1", "Organization/3"]
