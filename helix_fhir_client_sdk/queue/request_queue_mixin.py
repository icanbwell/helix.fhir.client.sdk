from __future__ import annotations
from __future__ import annotations

import logging
import time
from abc import ABC
from asyncio import Semaphore
from typing import (
    Dict,
    Optional,
    List,
    Any,
    AsyncGenerator,
)

from helix_fhir_client_sdk.exceptions.fhir_sender_exception import FhirSenderException
from helix_fhir_client_sdk.function_types import (
    HandleStreamingChunkFunction,
)
from helix_fhir_client_sdk.responses.fhir_client_protocol import FhirClientProtocol
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.fhir_response_processor import (
    FhirResponseProcessor,
)
from helix_fhir_client_sdk.structures.get_access_token_result import (
    GetAccessTokenResult,
)
from helix_fhir_client_sdk.utilities.fhir_client_logger import FhirClientLogger
from helix_fhir_client_sdk.utilities.retryable_aiohttp_client import (
    RetryableAioHttpClient,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_response import (
    RetryableAioHttpResponse,
)
from helix_fhir_client_sdk.utilities.url_checker import UrlChecker


class RequestQueueMixin(ABC, FhirClientProtocol):

    def __init__(self) -> None:
        self._max_concurrent_requests: Optional[int] = None
        self._max_concurrent_requests_semaphore: Optional[Semaphore] = None

    def set_max_concurrent_requests(
        self, max_concurrent_requests: Optional[int]
    ) -> "FhirClientProtocol":
        """
        Sets the maximum number of concurrent requests to make to the FHIR server

        :param max_concurrent_requests: maximum number of concurrent requests to make to the FHIR server

        """
        self._max_concurrent_requests = max_concurrent_requests
        if max_concurrent_requests:
            self._max_concurrent_requests_semaphore = Semaphore(max_concurrent_requests)
        return self

    async def _get_with_session_async(
        self,
        page_number: Optional[int],
        ids: Optional[List[str]],
        id_above: Optional[str],
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction],
        additional_parameters: Optional[List[str]],
        resource_type: Optional[str],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        issues a GET call with the specified session, page_number and ids


        :param page_number:
        :param ids:
        :param id_above: return ids greater than this
        :param fn_handle_streaming_chunk: function to call for each chunk of data
        :param additional_parameters: additional parameters to add to the request
        :return: response
        """
        assert self._url, "No FHIR server url was set"
        assert resource_type or self._resource, "No Resource was set"
        request_id: Optional[str] = None

        # create url and query to request from FHIR server
        resources_json: str = ""
        full_url = await self.build_url(
            ids=ids,
            id_above=id_above,
            page_number=page_number,
            additional_parameters=additional_parameters,
            resource_type=resource_type or self._resource,
        )

        # set up headers
        payload: Dict[str, str] | None = (
            self._action_payload if self._action_payload else None
        )
        headers = {
            "Accept": self._accept,
            "Content-Type": self._content_type,
            "Accept-Encoding": self._accept_encoding,
        }
        headers.update(self._additional_request_headers)
        self._internal_logger.debug(f"Request headers: {headers}")

        start_time: float = time.time()
        last_status_code: Optional[int] = None
        last_response_text: Optional[str] = None
        next_url: Optional[str] = full_url
        try:
            await FhirResponseProcessor.log_request(
                full_url=full_url,
                client_id=self._client_id,
                auth_scopes=self._auth_scopes,
                log_level=self._log_level,
                uuid=self._uuid,
                logger=self._logger,
                internal_logger=self._internal_logger,
            )

            async with RetryableAioHttpClient(
                fn_get_session=lambda: self.create_http_session(),
                refresh_token_func=self._refresh_token_function,
                tracer_request_func=self._trace_request_function,
                retries=self._retry_count,
                exclude_status_codes_from_retry=self._exclude_status_codes_from_retry,
                use_data_streaming=self._use_data_streaming,
                compress=self._compress,
                throw_exception_on_error=self._throw_exception_on_error,
                log_all_url_results=self._log_all_response_urls,
                access_token=self._access_token,
                access_token_expiry_date=self._access_token_expiry_date,
            ) as client:
                while next_url:
                    # set access token in request if present
                    access_token_result: GetAccessTokenResult = (
                        await self.get_access_token_async()
                    )
                    access_token: Optional[str] = access_token_result.access_token
                    if access_token:
                        headers["Authorization"] = f"Bearer {access_token}"

                    if not UrlChecker.is_absolute_url(url=next_url):
                        next_url = UrlChecker.convert_relative_url_to_absolute_url(
                            base_url=self._url, relative_url=next_url
                        )
                    response: RetryableAioHttpResponse = (
                        await self._send_fhir_request_async(
                            client=client,
                            full_url=next_url,
                            headers=headers,
                            payload=payload,
                        )
                    )
                    assert isinstance(response, RetryableAioHttpResponse)

                    if response.access_token:
                        access_token = response.access_token
                        self.set_access_token(response.access_token)
                    if response.access_token_expiry_date:
                        self.set_access_token_expiry_date(
                            response.access_token_expiry_date
                        )

                    last_status_code = response.status
                    response_headers: List[str] = [
                        f"{key}:{value}"
                        for key, value in response.response_headers.items()
                    ]
                    await FhirResponseProcessor.log_response(
                        full_url=next_url,
                        response_status=response.status,
                        client_id=self._client_id,
                        internal_logger=self._internal_logger,
                        log_level=self._log_level,
                        logger=self._logger,
                        auth_scopes=self._auth_scopes,
                        uuid=self._uuid,
                    )

                    request_id = response.response_headers.get("X-Request-ID", None)
                    self._internal_logger.info(f"X-Request-ID={request_id}")

                    async for r in FhirResponseProcessor.handle_response(
                        internal_logger=self._internal_logger,
                        access_token=access_token,
                        response_headers=response_headers,
                        response=response,
                        logger=self._logger,
                        resources_json=resources_json,
                        full_url=next_url,
                        request_id=request_id,
                        resource=resource_type or self._resource,
                        id_=self._id,
                        chunk_size=self._chunk_size,
                        expand_fhir_bundle=self._expand_fhir_bundle,
                        separate_bundle_resources=self._separate_bundle_resources,
                        url=self._url,
                        extra_context_to_return=self._extra_context_to_return,
                        use_data_streaming=self._use_data_streaming,
                        fn_handle_streaming_chunk=fn_handle_streaming_chunk,
                        storage_mode=self._storage_mode,
                        create_operation_outcome_for_error=self._create_operation_outcome_for_error,
                    ):
                        next_url = r.next_url
                        yield r

        except Exception as ex:
            raise FhirSenderException(
                request_id=request_id,
                exception=ex,
                url=str(next_url),
                headers=headers,
                json_data="",
                variables=FhirClientLogger.get_variables_to_log(vars(self)),
                response_text=last_response_text,
                response_status_code=last_status_code,
                message="",
                elapsed_time=time.time() - start_time,
            )

    # noinspection PyProtocol
    async def _send_fhir_request_async(
        self,
        *,
        client: RetryableAioHttpClient,
        full_url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any] | None,
    ) -> RetryableAioHttpResponse:
        """
        Sends a request to the server


        :param full_url: url to call
        :param headers: headers to send
        :param payload: payload to send
        """
        if self._max_concurrent_requests_semaphore:
            async with self._max_concurrent_requests_semaphore:
                return await self._send_fhir_request_internal_async(
                    client=client,
                    full_url=full_url,
                    headers=headers,
                    payload=payload,
                )
        else:
            return await self._send_fhir_request_internal_async(
                client=client, full_url=full_url, headers=headers, payload=payload
            )

    async def _send_fhir_request_internal_async(
        self,
        *,
        client: RetryableAioHttpClient,
        full_url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any] | None,
    ) -> RetryableAioHttpResponse:
        """
        Sends a request to the server


        :param full_url: url to call
        :param headers: headers to send
        :param payload: payload to send
        """
        assert client is not None
        assert full_url
        assert headers
        assert isinstance(headers, dict)
        if payload:
            assert isinstance(payload, dict)

        if self._action == "$graph":
            if self._logger:
                self._logger.info(
                    f"sending a post: {full_url} with client_id={self._client_id} and scopes={self._auth_scopes}"
                )
            logging.info(
                f"sending a post: {full_url} with client_id={self._client_id} and scopes={self._auth_scopes}"
            )
            if payload:
                return await client.post(url=full_url, headers=headers, json=payload)
            else:
                raise Exception(
                    "$graph needs a payload to define the returning response (use action_payload parameter)"
                )
        else:
            if self._log_level == "DEBUG":
                if self._logger:
                    self._logger.info(
                        f"sending a get: {full_url} with client_id={self._client_id} "
                        + f"and scopes={self._auth_scopes} instance_id={self._uuid}"
                    )
                else:
                    self._internal_logger.info(
                        f"sending a get: {full_url} with client_id={self._client_id} "
                        + f"and scopes={self._auth_scopes} instance_id={self._uuid}"
                    )
            return await client.get(url=full_url, headers=headers, data=payload)
