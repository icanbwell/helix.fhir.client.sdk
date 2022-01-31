import json
from typing import Optional, Dict

from aioresponses import aioresponses, CallbackResult
from yarl import URL

from helix_fhir_client_sdk.async_fhir_client import AsyncFhirClient
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse


async def test_async_fhir_client_patient_merge() -> None:
    mock: aioresponses
    with aioresponses() as mock:  # type: ignore
        url = "http://foo"
        request_data = {"resourceType": "Patient", "id": "12355"}
        response_json = [{"created": 1, "updated": 0}]

        def custom_matcher(
            url_: URL, allow_redirects: bool, data: bytes, headers: Dict[str, str]
        ) -> Optional[CallbackResult]:
            if url_.path == "/Patient/1/$merge" and data.decode("utf8") == json.dumps(
                [request_data]
            ):
                return CallbackResult(status=200, payload=response_json)  # type: ignore
            return None

        mock.post(
            f"{url}/Patient/1/$merge",
            callback=custom_matcher,
            payload=f"{json.dumps(response_json)}",
        )

        fhir_client = AsyncFhirClient()
        fhir_client = fhir_client.url(url).resource("Patient")
        response: FhirMergeResponse = await fhir_client.merge(
            [json.dumps(request_data)]
        )

        print(response.responses)
        assert response.responses == response_json
