import json
from typing import Dict, Optional, List

from furl import furl

from helix_fhir_client_sdk.responses.fhir_client_protocol import FhirClientProtocol
from helix_fhir_client_sdk.responses.fhir_delete_response import FhirDeleteResponse
from helix_fhir_client_sdk.utilities.async_runner import AsyncRunner
from helix_fhir_client_sdk.utilities.retryable_aiohttp_client import (
    RetryableAioHttpClient,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_response import (
    RetryableAioHttpResponse,
)


class FhirDeleteMixin(FhirClientProtocol):
    async def delete_async(self) -> FhirDeleteResponse:
        """
        Delete the resources

        """
        id_list = self._id
        if isinstance(id_list, list):
            id_list = ",".join(id_list)
        if not id_list:
            raise ValueError("delete requires the ID of FHIR object to delete")
        if not self._resource:
            raise ValueError("delete requires a FHIR resource type")
        full_uri: furl = furl(self._url)
        full_uri /= self._resource
        full_uri /= id_list
        # setup retry
        # set up headers
        headers: Dict[str, str] = {}
        headers.update(self._additional_request_headers)
        self._internal_logger.debug(f"Request headers: {headers}")

        access_token = await self.get_access_token_async()
        # set access token in request if present
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        async with RetryableAioHttpClient(
            fn_get_session=lambda: self.create_http_session(),
            simple_refresh_token_func=lambda: self._refresh_token_function(),
            retries=self._retry_count,
            exclude_status_codes_from_retry=self._exclude_status_codes_from_retry,
            use_data_streaming=self._use_data_streaming,
            compress=False,
            throw_exception_on_error=self._throw_exception_on_error,
        ) as client:
            response: RetryableAioHttpResponse = await client.delete(
                url=full_uri.tostr(), headers=headers
            )
            request_id = response.response_headers.get("X-Request-ID", None)
            self._internal_logger.info(f"X-Request-ID={request_id}")
            if response.status == 200:
                if self._logger:
                    self._logger.info(f"Successfully deleted: {full_uri}")

            return FhirDeleteResponse(
                request_id=request_id,
                url=full_uri.tostr(),
                responses=await response.get_text_async(),
                error=f"{response.status}" if not response.status == 200 else None,
                access_token=access_token,
                status=response.status,
                resource_type=self._resource,
            )

    def delete(self) -> FhirDeleteResponse:
        """
        Delete the resources

        """
        result: FhirDeleteResponse = AsyncRunner.run(self.delete_async())
        return result

    async def delete_by_query_async(
        self, *, additional_parameters: Optional[List[str]] = None
    ) -> FhirDeleteResponse:
        """
        Delete the resources using the specified query if any


        :param additional_parameters: additional parameters to add to the query
        :return: response
        """
        if not self._resource:
            raise ValueError("delete requires a FHIR resource type")
        full_uri: furl = furl(self._url)
        full_uri /= self._resource
        full_url = await self.build_url(
            id_above=None,
            page_number=None,
            ids=None,
            additional_parameters=additional_parameters,
        )
        # setup retry
        # set up headers
        headers: Dict[str, str] = {}
        headers.update(self._additional_request_headers)
        self._internal_logger.debug(f"Request headers: {headers}")

        access_token = await self.get_access_token_async()
        # set access token in request if present
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        async with RetryableAioHttpClient(
            fn_get_session=lambda: self.create_http_session(),
            simple_refresh_token_func=lambda: self._refresh_token_function(),
            retries=self._retry_count,
            exclude_status_codes_from_retry=self._exclude_status_codes_from_retry,
            use_data_streaming=self._use_data_streaming,
            compress=False,
            throw_exception_on_error=self._throw_exception_on_error,
        ) as client:
            response: RetryableAioHttpResponse = await client.delete(
                url=full_url, headers=headers
            )
            request_id = response.response_headers.get("X-Request-ID", None)
            self._internal_logger.info(f"X-Request-ID={request_id}")
            if response.status == 200:
                if self._logger:
                    self._logger.info(f"Successfully deleted: {full_uri}")

            deleted_count: Optional[int] = None
            response_text = await response.get_text_async()
            if response_text and response_text.startswith("{"):
                # '{"deleted":0}'
                deleted_info = json.loads(response_text)
                deleted_count = deleted_info.get("deleted", None)

            return FhirDeleteResponse(
                request_id=request_id,
                url=full_url,
                responses=response_text,
                error=f"{response.status}" if not response.status == 200 else None,
                access_token=access_token,
                status=response.status,
                count=deleted_count,
                resource_type=self._resource,
            )
