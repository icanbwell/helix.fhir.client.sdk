from typing import Deque

from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource


class FhirResourceList(Deque[FhirResource]):
    pass
