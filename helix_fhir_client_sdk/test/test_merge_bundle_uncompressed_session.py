"""Regression test ensuring merge_bundle_uncompressed() honors a caller-supplied
HTTP session factory (FhirClient.use_http_session()), matching the session
management behavior of its sibling merge call sites (merge_bundle_async,
merge_resources_async). Without this, a caller-provided session is silently
ignored - the SDK creates its own session instead - and the caller's session
lifecycle expectations are violated.
"""

import aiohttp
import pytest
from aioresponses import aioresponses
from compressedfhir.fhir.fhir_bundle import FhirBundle
from compressedfhir.fhir.fhir_bundle_entry import FhirBundleEntry
from compressedfhir.fhir.fhir_bundle_entry_list import FhirBundleEntryList
from compressedfhir.fhir.fhir_resource import FhirResource

from helix_fhir_client_sdk.fhir_client import FhirClient


@pytest.mark.asyncio
async def test_merge_bundle_uncompressed_uses_caller_provided_session() -> None:
    url = "http://example.com/Patient/1/$merge"
    user_session = aiohttp.ClientSession()
    factory_call_count = 0

    def session_factory() -> aiohttp.ClientSession:
        nonlocal factory_call_count
        factory_call_count += 1
        return user_session

    try:
        fhir_client = (
            FhirClient()
            .url("http://example.com")
            .resource("Patient")
            .use_http_session(session_factory)
            .set_access_token("test-token")
        )
        bundle = FhirBundle(
            type_="batch",
            entry=FhirBundleEntryList([FhirBundleEntry(resource=FhirResource({"resourceType": "Patient", "id": "1"}))]),
        )

        with aioresponses() as m:
            m.post(url, status=200, payload={"resourceType": "Patient", "id": "1"})

            await fhir_client.merge_bundle_uncompressed(id_="1", bundle=bundle)

        # The caller-provided factory must be the one used to create the session ...
        assert factory_call_count == 1
        # ... and, since the caller supplied it, the SDK must not close it.
        assert not user_session.closed
    finally:
        await user_session.close()
