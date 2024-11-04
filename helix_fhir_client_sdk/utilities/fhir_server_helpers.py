from os import environ


from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_delete_response import FhirDeleteResponse


class FhirServerHelpers:
    @staticmethod
    async def clean_fhir_server_async(
        resource_type: str, owner_tag: str = "bwell"
    ) -> None:
        # clean the fhir server
        fhir_server_url: str = environ["FHIR_SERVER_URL"]
        auth_client_id = environ["FHIR_CLIENT_ID"]
        auth_client_secret = environ["FHIR_CLIENT_SECRET"]
        auth_well_known_url = environ["AUTH_CONFIGURATION_URI"]
        fhir_client = FhirClient()
        fhir_client = fhir_client.client_credentials(
            client_id=auth_client_id, client_secret=auth_client_secret
        )
        fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)

        response: FhirDeleteResponse = (
            await fhir_client.url(fhir_server_url)
            .resource(resource_type)
            .additional_parameters(
                [f"_security=https://www.icanbwell.com/owner|{owner_tag}"]
            )
            # .additional_parameters(["source=http://www.icanbwell.com"])
            .delete_by_query_async()
        )
        assert response.status == 200, response.responses
        print(f"Deleted {response.count} {resource_type} resources")
