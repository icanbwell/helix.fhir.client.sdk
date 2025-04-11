import json
import time
from typing import Optional

from furl import furl

from helix_fhir_client_sdk.exceptions.fhir_sender_exception import FhirSenderException
from helix_fhir_client_sdk.responses.fhir_client_protocol import FhirClientProtocol
from helix_fhir_client_sdk.responses.fhir_update_response import FhirUpdateResponse
from helix_fhir_client_sdk.structures.get_access_token_result import (
    GetAccessTokenResult,
)
from helix_fhir_client_sdk.utilities.async_runner import AsyncRunner
from helix_fhir_client_sdk.utilities.fhir_client_logger import FhirClientLogger
from helix_fhir_client_sdk.utilities.retryable_aiohttp_client import (
    RetryableAioHttpClient,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_response import (
    RetryableAioHttpResponse,
)


class FhirPatchMixin(FhirClientProtocol):
    async def send_patch_request_async(self, data: str) -> FhirUpdateResponse:
        """
        Update the resource.  This will partially update an existing resource with changes specified in the request.
        :param data: data to update the resource with
        """
        assert self._url, "No FHIR server url was set"
        assert data, "Empty string was passed"
        if not self._id:
            raise ValueError("update requires the ID of FHIR object to update")
        if not isinstance(self._id, str):
            raise ValueError("update should have only one id")
        if not self._resource:
            raise ValueError("update requires a FHIR resource type")
        self._internal_logger.debug(
            f"Calling patch method on {self._url} with client_id={self._client_id} and scopes={self._auth_scopes}"
        )
        full_uri: furl = furl(self._url)
        full_uri /= self._resource
        full_uri /= self._id
        request_id: Optional[str] = None

        start_time: float = time.time()

        # Set up headers
        headers = {"Content-Type": "application/json-patch+json"}
        headers.update(self._additional_request_headers)
        self._internal_logger.debug(f"Request headers: {headers}")
        access_token_result: GetAccessTokenResult = await self.get_access_token_async()
        access_token: Optional[str] = access_token_result.access_token
        # set access token in request if present
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        response_text: Optional[str] = None
        response_status: Optional[int] = None

        try:
            deserialized_data = json.loads(data)
            # actually make the request
            async with RetryableAioHttpClient(
                fn_get_session=lambda: self.create_http_session(),
                refresh_token_func=self._refresh_token_function,
                tracer_request_func=self._trace_request_function,
                retries=self._retry_count,
                exclude_status_codes_from_retry=self._exclude_status_codes_from_retry,
                use_data_streaming=self._use_data_streaming,
                send_data_as_chunked=self._send_data_as_chunked,
                compress=self._compress,
                throw_exception_on_error=self._throw_exception_on_error,
                log_all_url_results=self._log_all_response_urls,
                access_token=self._access_token,
                access_token_expiry_date=self._access_token_expiry_date,
            ) as client:
                response: RetryableAioHttpResponse = await client.patch(
                    url=full_uri.url, json=deserialized_data, headers=headers
                )
                response_status = response.status
                response_text = await response.get_text_async()
                request_id = response.response_headers.get("X-Request-ID", None)
                self._internal_logger.info(f"X-Request-ID={request_id}")

                if response_status == 200:
                    if self._logger:
                        self._logger.info(f"Successfully updated: {full_uri}")
                elif response_status == 404:
                    if self._logger:
                        self._logger.info(f"Request resource was not found: {full_uri}")
                else:
                    # other HTTP errors
                    self._internal_logger.info(
                        f"PATCH response for {full_uri.url}: {response_status}"
                    )
        except Exception as e:
            raise FhirSenderException(
                request_id=request_id,
                url=full_uri.url,
                headers=headers,
                json_data=data,
                response_text=response_text,
                response_status_code=response_status,
                exception=e,
                variables=FhirClientLogger.get_variables_to_log(vars(self)),
                message=f"Error: {e}",
                elapsed_time=time.time() - start_time,
            ) from e
        # check if response is json
        if response_text:
            try:
                responses = json.loads(response_text)
            except ValueError as e:
                responses = {"issue": str(e)}
        else:
            responses = {}
        return FhirUpdateResponse(
            request_id=request_id,
            url=full_uri.tostr(),
            responses=json.dumps(responses),
            error=json.dumps(responses),
            access_token=access_token,
            status=response_status if response_status else 500,
            resource_type=self._resource,
        )

    def send_patch_request(self, data: str) -> FhirUpdateResponse:
        """
        Update the resource.  This will partially update an existing resource with changes specified in the request.
        :param data: data to update the resource with
        """
        result: FhirUpdateResponse = AsyncRunner.run(
            self.send_patch_request_async(data)
        )
        return result
