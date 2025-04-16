from collections.abc import Callable
from typing import Any, cast

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
        access_token: str | None,
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
            access_token=access_token,
            access_token_expiry_date=None,
            refresh_token_func=None,
            tracer_request_func=None,
        ) as client:
            validation_response: RetryableAioHttpResponse = await client.post(
                url=full_validation_uri.url,
                data=json_data,
                headers=headers,
            )
            request_id = validation_response.response_headers.get("X-Request-ID")
            if validation_response.ok:
                operation_outcome: dict[str, Any] = cast(dict[str, Any], await validation_response.json())
                issue: list[dict[str, Any]] = operation_outcome.get("issue", [])
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
