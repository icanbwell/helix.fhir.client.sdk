from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


def test_dev_server_auth() -> None:
    url = "https://fhir-auth.dev.bwell.zone/4_0_0"
    fhir_client = FhirClient()
    fhir_client = fhir_client.url(url).resource("Patient")
    fhir_client = fhir_client.client_credentials(
        client_id="4opocimdhppokn1ks0hpbo9fkv",
        client_secret="439agu0s6oophr1j2bha284r6m9fbbo95m55d4dadae28do99bl",
    ).auth_scopes(["user/*.read"])
    response: FhirGetResponse = fhir_client.get()
    print(response.responses)
