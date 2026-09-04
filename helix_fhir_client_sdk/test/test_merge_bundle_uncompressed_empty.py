"""Regression test for an empty Bundle passed to merge_bundle_uncompressed().

Found during adversarial review: unlike its sibling merge_bundle_async (which
guards `len(bundle.entry) > 0` and yields a graceful "No resources to send"
response), merge_bundle_uncompressed unconditionally accessed `bundle.entry[0]`,
raising an uncaught IndexError - not even wrapped in FhirSenderException - for an
empty bundle.
"""

import pytest
from compressedfhir.fhir.fhir_bundle import FhirBundle
from compressedfhir.fhir.fhir_bundle_entry_list import FhirBundleEntryList

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.merge.fhir_merge_resource_response import (
    FhirMergeResourceResponse,
)


@pytest.mark.asyncio
async def test_merge_bundle_uncompressed_with_empty_bundle_does_not_raise() -> None:
    fhir_client = FhirClient().url("http://example.com").resource("Patient")
    bundle = FhirBundle(type_="batch", entry=FhirBundleEntryList([]))

    merge_response: FhirMergeResourceResponse = await fhir_client.merge_bundle_uncompressed(id_="1", bundle=bundle)

    assert merge_response.error == "No resources to send"
    assert len(merge_response.responses) == 0
