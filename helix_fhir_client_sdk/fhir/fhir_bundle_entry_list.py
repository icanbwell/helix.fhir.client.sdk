from typing import Deque

from helix_fhir_client_sdk.fhir.bundle_entry import BundleEntry


class FhirBundleEntryList(Deque[BundleEntry]):
    pass
