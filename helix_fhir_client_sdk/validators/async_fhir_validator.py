from typing import Dict, Any, Optional, Callable, List, cast

from aiohttp import ClientSession
from furl import furl

from helix_fhir_client_sdk.exceptions.fhir_validation_exception import (
    FhirValidationException,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_client import (
    RetryableAioHttpClient,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_response import (
    RetryableAioHttpResponse,
)


class AsyncFhirValidator:
    @staticmethod
    async def validate_fhir_resource(
        fn_get_session: Callable[[], ClientSession],
        json_data: str,
        resource_name: str,
        validation_server_url: str,
        access_token: Optional[str],
    ) -> None:
        """
        Calls the validation server url to validate the given resource

        :param fn_get_session: function to get the aiohttp session
        :param json_data: json data for resource
        :param resource_name: name of resource
        :param validation_server_url: url to validation server
        :param access_token: access token to use
        """
        # check each resource against the validation server
        headers = {"Content-Type": "application/fhir+json"}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        full_validation_uri: furl = furl(validation_server_url)
        full_validation_uri /= resource_name
        full_validation_uri /= "$validate"
        async with RetryableAioHttpClient(
            fn_get_session=fn_get_session,
            use_data_streaming=False,
        ) as http:
            validation_response: RetryableAioHttpResponse = await http.post(
                url=full_validation_uri.url,
                data=json_data,
                headers=headers,
            )
            request_id = validation_response.response_headers.get("X-Request-ID")
            if validation_response.ok:
                operation_outcome: Dict[str, Any] = cast(
                    Dict[str, Any], await validation_response.json()
                )
                issue: List[Dict[str, Any]] = operation_outcome.get("issue", [])
                if len(issue) > 0 and issue[0].get("severity") == "error":
                    response_text = await validation_response.get_text_async()
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
                response_text = await validation_response.get_text_async()
                raise FhirValidationException(
                    request_id=request_id,
                    url=full_validation_uri.url,
                    json_data=json_data,
                    response_text=response_text,
                    response_status_code=validation_response.status,
                    message="FhirSender: Validation Failed",
                    headers=headers,
                    issue=[
                        {
                            "severity": "error",
                            "code": "invalid",
                            "details": response_text,
                        }
                    ],
                )
