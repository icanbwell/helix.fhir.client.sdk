import asyncio
from typing import Dict, Optional, List

from furl import furl

from helix_fhir_client_sdk.responses.fhir_client_protocol import FhirClientProtocol
from helix_fhir_client_sdk.responses.fhir_delete_response import FhirDeleteResponse
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
        if not self._id:
            raise ValueError("delete requires the ID of FHIR object to delete")
        if not self._resource:
            raise ValueError("delete requires a FHIR resource type")
        full_uri: furl = furl(self._url)
        full_uri /= self._resource
        full_uri /= self._id
        # setup retry
        async with self.create_http_session() as http:
            # set up headers
            headers: Dict[str, str] = {}
            headers.update(self._additional_request_headers)
            self._internal_logger.debug(f"Request headers: {headers}")

            access_token = await self.get_access_token_async()
            # set access token in request if present
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"

            client: RetryableAioHttpClient = RetryableAioHttpClient(
                session=http,
                simple_refresh_token_func=lambda: self._refresh_token_function(
                    auth_server_url=self._auth_server_url,
                    auth_scopes=self._auth_scopes,
                    login_token=self._login_token,
                ),
                retries=self._retry_count,
                exclude_status_codes_from_retry=self._exclude_status_codes_from_retry,
                use_data_streaming=self._use_data_streaming,
            )

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
            )

    def delete(self) -> FhirDeleteResponse:
        """
        Delete the resources

        """
        result: FhirDeleteResponse = asyncio.run(self.delete_async())
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
        full_url: str = full_uri.url
        if additional_parameters:
            if len(full_uri.args) > 0:
                full_url += "&"
            else:
                full_url += "?"
            full_url += "&".join(additional_parameters)
        elif self._additional_parameters:
            if len(full_uri.args) > 0:
                full_url += "&"
            else:
                full_url += "?"
            full_url += "&".join(self._additional_parameters)
        # setup retry
        async with self.create_http_session() as http:
            # set up headers
            headers: Dict[str, str] = {}
            headers.update(self._additional_request_headers)
            self._internal_logger.debug(f"Request headers: {headers}")

            access_token = await self.get_access_token_async()
            # set access token in request if present
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"

            client: RetryableAioHttpClient = RetryableAioHttpClient(
                session=http,
                simple_refresh_token_func=lambda: self._refresh_token_function(
                    auth_server_url=self._auth_server_url,
                    auth_scopes=self._auth_scopes,
                    login_token=self._login_token,
                ),
                retries=self._retry_count,
                exclude_status_codes_from_retry=self._exclude_status_codes_from_retry,
                use_data_streaming=self._use_data_streaming,
            )

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
            )
