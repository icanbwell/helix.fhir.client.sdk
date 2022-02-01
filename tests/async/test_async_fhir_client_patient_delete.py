from typing import Dict, Optional

from aiohttp import ClientResponse
from aioresponses import aioresponses, CallbackResult
from yarl import URL

from helix_fhir_client_sdk.async_fhir_client import AsyncFhirClient


async def test_async_fhir_client_patient_delete() -> None:
    mock: aioresponses
    with aioresponses() as mock:  # type: ignore
        # Arrange
        url = "http://foo"

        def delete_matcher(
            url_: URL, allow_redirects: bool, headers: Dict[str, str]
        ) -> Optional[CallbackResult]:
            if url_.path == "/Patient/12345":
                return CallbackResult(status=204)
            return None

        mock.delete(url=f"{url}/Patient/12345", callback=delete_matcher)

        # Act
        fhir_client = AsyncFhirClient()
        fhir_client = fhir_client.url(url).resource("Patient").id_("12345")
        response: ClientResponse = await fhir_client.delete()

        # Assert
        response.raise_for_status()
        assert response.status == 204
