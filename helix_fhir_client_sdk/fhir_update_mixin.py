from collections.abc import AsyncGenerator

from compressedfhir.fhir.fhir_resource import FhirResource
from compressedfhir.fhir.fhir_resource_list import FhirResourceList
from furl import furl

from helix_fhir_client_sdk.responses.fhir_client_protocol import FhirClientProtocol
from helix_fhir_client_sdk.responses.fhir_update_response import FhirUpdateResponse
from helix_fhir_client_sdk.structures.get_access_token_result import (
    GetAccessTokenResult,
)
from helix_fhir_client_sdk.utilities.async_runner import AsyncRunner
from helix_fhir_client_sdk.utilities.retryable_aiohttp_client import (
    RetryableAioHttpClient,
)
from helix_fhir_client_sdk.validators.async_fhir_validator import AsyncFhirValidator


class FhirUpdateMixin(FhirClientProtocol):
    async def update_single_resource_async(self, *, resource: FhirResource) -> FhirUpdateResponse:
        """
        Update a single resource. This will completely overwrite the resource. We recommend using merge()
            instead since that does proper merging.

        :param resource: resource to update
        :return: FhirUpdateResponse object
        """
        if not resource.id:
            raise ValueError("Resource ID is required for update")
        json_data = resource.json()
        response = await self.update_async(json_data=json_data, id_=resource.id)
        if response.error:
            raise ValueError(f"Failed to update resource: {response.error}")
        return response

    async def update_resources_async(self, *, resources: FhirResourceList) -> AsyncGenerator[FhirUpdateResponse, None]:
        """
        Update the resources. This will completely overwrite the resources. We recommend using merge()
            instead since that does proper merging.

        :param resources: list of resources to update
        :return: generator of FhirUpdateResponses
        """
        resource: FhirResource
        for resource in resources:
            if not resource.id:
                raise ValueError("Resource ID is required for update")
            json_data = resource.json()
            response = await self.update_async(json_data=json_data, id_=resource.id)
            if response.error:
                raise ValueError(f"Failed to update resource: {response.error}")
            yield response

    async def update_async(self, *, id_: str | None = None, json_data: str) -> FhirUpdateResponse:
        """
        Update the resource.  This will completely overwrite the resource.  We recommend using merge()
            instead since that does proper merging.


        :param json_data: data to update the resource with
        :param id_: ID of the resource to update
        :return: FhirUpdateResponse object
        """
        assert self._url, "No FHIR server url was set"
        assert json_data, "Empty string was passed"
        if not id_ and not self._id:
            raise ValueError("update requires the ID of FHIR object to update")
        if not isinstance(self._id, str):
            raise ValueError("update should have only one id")
        if not self._resource:
            raise ValueError("update requires a FHIR resource type")
        full_uri: furl = furl(self._url)
        full_uri /= self._resource
        full_uri /= id_ or self._id
        # set up headers
        headers = {"Content-Type": "application/fhir+json"}
        headers.update(self._additional_request_headers)
        self._internal_logger.debug(f"Request headers: {headers}")

        access_token_result: GetAccessTokenResult = await self.get_access_token_async()
        access_token: str | None = access_token_result.access_token
        # set access token in request if present
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        if self._validation_server_url:
            await AsyncFhirValidator.validate_fhir_resource(
                fn_get_session=lambda: self.create_http_session(),
                json_data=json_data,
                resource_name=self._resource,
                validation_server_url=self._validation_server_url,
                access_token=access_token,
            )

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
            response = await client.put(url=full_uri.url, data=json_data, headers=headers)
            request_id = response.response_headers.get("X-Request-ID", None)
            self._internal_logger.info(f"X-Request-ID={request_id}")
            if response.status == 200:
                if self._logger:
                    self._logger.info(f"Successfully updated: {full_uri}")

            return FhirUpdateResponse(
                request_id=request_id,
                url=full_uri.tostr(),
                responses=await response.get_text_async(),
                error=f"{response.status}" if not response.status == 200 else None,
                access_token=access_token,
                status=response.status,
                resource_type=self._resource,
            )

    def update(self, json_data: str) -> FhirUpdateResponse:
        """
        Update the resource.  This will completely overwrite the resource.  We recommend using merge()
            instead since that does proper merging.


        :param json_data: data to update the resource with
        """
        result: FhirUpdateResponse = AsyncRunner.run(self.update_async(json_data=json_data))
        return result
