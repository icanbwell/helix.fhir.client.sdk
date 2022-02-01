import json
from builtins import bytes
from typing import Dict, Optional

from aiohttp import ClientResponse
from aioresponses import aioresponses, CallbackResult
from yarl import URL

from helix_fhir_client_sdk.async_fhir_client import AsyncFhirClient


async def test_async_fhir_client_patient_update() -> None:
    mock: aioresponses
    with aioresponses() as mock:  # type: ignore
        url = "http://foo"
        request_data = {"resourceType": "Patient", "id": "12355"}
        response_json = [{"created": 1, "updated": 0}]

        def custom_matcher(
            url_: URL, allow_redirects: bool, data: bytes, headers: Dict[str, str]
        ) -> Optional[CallbackResult]:
            if url_.path == "/Patient/12355" and data.decode("utf8") == json.dumps(
                request_data
            ):
                resp: CallbackResult = CallbackResult(status=200)
                return resp
            return None

        mock.put(
            f"{url}/Patient/12355",
            callback=custom_matcher,
            payload=f"{json.dumps(response_json)}",
        )

        fhir_client = AsyncFhirClient()
        fhir_client = fhir_client.url(url).resource("Patient")
        fhir_client = fhir_client.id_(request_data["id"])
        response: ClientResponse = await fhir_client.update(json.dumps(request_data))

        assert response.ok
