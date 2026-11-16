"""
DCON-6330: paging follows a same-host next link over the client's own scheme

End to end through FhirClient.get_raw_resources_async(), with HTTP mocked at the
boundary (aioresponses). Page 1 returns a Bundle whose next link is https:// on the
same host, as a FHIR server behind a TLS-terminating proxy writes it. The client was
configured with http://, so page 2 must be requested over http://. aioresponses
refuses any URL that is not mocked, so a request to https:// fails the test.
"""

import re
from typing import Any

from aioresponses import aioresponses

from helix_fhir_client_sdk.fhir_client import FhirClient

BASE_URL = "http://fhir-server/4_0_0"
FIRST_PAGE = re.compile(r"^http://fhir-server/4_0_0/Patient(\?(?!.*above).*)?$")
SECOND_PAGE = re.compile(r"^http://fhir-server/4_0_0/Patient\?.*id(:|%3A)above=p1")


def _bundle(resource_id: str, next_url: str | None = None) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [{"resource": {"resourceType": "Patient", "id": resource_id}}],
    }
    if next_url:
        bundle["link"] = [{"relation": "next", "url": next_url}]
    return bundle


async def test_https_next_link_is_followed_over_the_base_scheme() -> None:
    with aioresponses() as mocked:
        mocked.get(FIRST_PAGE, payload=_bundle("p1", next_url="https://fhir-server/4_0_0/Patient?id:above=p1"))
        mocked.get(SECOND_PAGE, payload=_bundle("p2"))
        fhir_client = FhirClient().url(BASE_URL).resource("Patient")

        result = await fhir_client.get_raw_resources_async()

        requested = [str(url) for (_method, url) in mocked.requests]

    assert result["status"] == 200
    assert [resource["id"] for resource in result["_resources"]] == ["p1", "p2"]
    assert all(url.startswith("http://fhir-server/") for url in requested), requested
