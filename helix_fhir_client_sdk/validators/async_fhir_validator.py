from typing import Dict, Any

from aiohttp import ClientSession, ClientResponse
from furl import furl

from helix_fhir_client_sdk.exceptions.fhir_validation_exception import (
    FhirValidationException,
)


class AsyncFhirValidator:
    @staticmethod
    async def validate_fhir_resource(
        http: ClientSession,
        json_data: str,
        resource_name: str,
        validation_server_url: str,
    ) -> None:
        """
        Calls the validation server url to validate the given resource

        :param http: Http Session to use
        :param json_data: json data for resource
        :param resource_name: name of resource
        :param validation_server_url: url to validation server
        """
        # check each resource against the validation server
        headers = {"Content-Type": "application/fhir+json"}
        full_validation_uri: furl = furl(validation_server_url)
        full_validation_uri /= resource_name
        full_validation_uri /= "$validate"
        validation_response: ClientResponse = await http.post(
            url=full_validation_uri.url,
            data=json_data.encode("utf-8"),
            headers=headers,
        )
        request_id = validation_response.headers.getone("X-Request-ID", None)
        if validation_response.ok:
            operation_outcome: Dict[str, Any] = await validation_response.json()
            if operation_outcome["issue"][0]["severity"] == "error":
                response_text = await validation_response.text()
                raise FhirValidationException(
                    request_id=request_id,
                    url=full_validation_uri.url,
                    json_data=json_data,
                    response_text=response_text,
                    response_status_code=validation_response.status,
                    message="FhirSender: Validation Failed",
                    headers=headers,
                    issue=operation_outcome["issue"],
                )
        else:
            response_text = await validation_response.text()
            raise FhirValidationException(
                request_id=request_id,
                url=full_validation_uri.url,
                json_data=json_data,
                response_text=response_text,
                response_status_code=validation_response.status,
                message="FhirSender: Validation Failed",
                headers=headers,
                issue=None,
            )
