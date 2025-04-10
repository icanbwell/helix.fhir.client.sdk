import json
import time
from datetime import datetime
from logging import Logger
from typing import Optional, List, Dict, Any, Union, AsyncGenerator, Tuple
from uuid import UUID

# noinspection PyProtectedMember
from aiohttp.streams import AsyncStreamIterator

from helix_fhir_client_sdk.function_types import (
    HandleStreamingChunkFunction,
)
from logging import Logger
from helix_fhir_client_sdk.responses.bundle_expander import (
    BundleExpander,
    BundleExpanderResult,
)
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.get.fhir_get_error_response import (
    FhirGetErrorResponse,
)
from helix_fhir_client_sdk.responses.get.fhir_get_response_factory import (
    FhirGetResponseFactory,
)
from helix_fhir_client_sdk.responses.resource_separator import (
    ResourceSeparator,
    ResourceSeparatorResult,
)
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from helix_fhir_client_sdk.utilities.ndjson_chunk_streaming_parser import (
    NdJsonChunkStreamingParser,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_response import (
    RetryableAioHttpResponse,
)


class FhirResponseProcessor:
    """
    This class is responsible for processing the response from the FHIR server.

    """

    @staticmethod
    async def handle_response(
        *,
        response: RetryableAioHttpResponse,
        full_url: str,
        request_id: Optional[str],
        response_headers: List[str],
        access_token: Optional[str],
        resources_json: str,
        fn_handle_streaming_chunk: HandleStreamingChunkFunction | None,
        logger: Optional[Logger],
        internal_logger: Optional[Logger],
        extra_context_to_return: Optional[Dict[str, Any]],
        resource: Optional[str],
        id_: Optional[Union[List[str], str]],
        chunk_size: int,
        expand_fhir_bundle: bool,
        url: Optional[str],
        separate_bundle_resources: bool,
        use_data_streaming: bool,
        storage_mode: CompressedDictStorageMode,
        create_operation_outcome_for_error: Optional[bool],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        This method is responsible for handling the response from the FHIR server.
        It returns an async generator of FhirGetResponse objects.

        :param response: The response object from the FHIR server.
        :param full_url: The full URL of the request.
        :param request_id: The request ID.
        :param response_headers: The response headers.
        :param access_token: The access token.
        :param resources_json: The resources in JSON format.
        :param fn_handle_streaming_chunk: The function to handle the streaming chunk.
        :param logger: The logger object.
        :param internal_logger: The internal logger object.
        :param extra_context_to_return: The extra context to return.
        :param resource: The resource type.
        :param id_: The ID of the resource.
        :param chunk_size: The chunk size.
        :param expand_fhir_bundle: Whether to expand the FHIR bundle.
        :param url: The URL.
        :param separate_bundle_resources: Whether to separate the bundle resources.
        :param use_data_streaming: Whether to use data streaming.
        :param storage_mode: The storage mode.
        :param create_operation_outcome_for_error: Whether to create an operation outcome for error.

        :return: An async generator of FhirGetResponse objects.
        """
        # if request is ok (200) then return the data
        if response.ok:
            async for r in FhirResponseProcessor._handle_response_200(
                full_url=full_url,
                request_id=request_id,
                response=response,
                response_headers=response_headers,
                fn_handle_streaming_chunk=fn_handle_streaming_chunk,
                access_token=access_token,
                resources_json=resources_json,
                resource=resource,
                id_=id_,
                logger=logger,
                use_data_streaming=use_data_streaming,
                chunk_size=chunk_size,
                extra_context_to_return=extra_context_to_return,
                expand_fhir_bundle=expand_fhir_bundle,
                url=url,
                separate_bundle_resources=separate_bundle_resources,
                storage_mode=storage_mode,
                create_operation_outcome_for_error=create_operation_outcome_for_error,
            ):
                yield r
        elif response.status == 404:  # not found
            async for r in FhirResponseProcessor._handle_response_404(
                full_url=full_url,
                request_id=request_id,
                response=response,
                response_headers=response_headers,
                extra_context_to_return=extra_context_to_return,
                resource=resource,
                logger=logger,
                id_=id_,
                access_token=access_token,
                storage_mode=storage_mode,
                create_operation_outcome_for_error=create_operation_outcome_for_error,
            ):
                yield r
        else:  # unknown response
            async for r in FhirResponseProcessor._handle_response_unknown(
                full_url=full_url,
                request_id=request_id,
                response=response,
                response_headers=response_headers,
                resource=resource,
                logger=logger,
                access_token=access_token,
                extra_context_to_return=extra_context_to_return,
                id_=id_,
                internal_logger=internal_logger,
                storage_mode=storage_mode,
                create_operation_outcome_for_error=create_operation_outcome_for_error,
            ):
                yield r

    @staticmethod
    async def _handle_response_unknown(
        *,
        full_url: str,
        request_id: Optional[str],
        response: RetryableAioHttpResponse,
        response_headers: List[str],
        logger: Optional[Logger],
        internal_logger: Optional[Logger],
        access_token: Optional[str],
        extra_context_to_return: Optional[Dict[str, Any]],
        resource: Optional[str],
        id_: Optional[Union[List[str], str]],
        storage_mode: CompressedDictStorageMode,
        create_operation_outcome_for_error: Optional[bool],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        This method is responsible for handling an unknown response from the FHIR server.

        :param full_url: The full URL of the request.
        :param request_id: The request ID.
        :param response: The response object from the FHIR server.
        :param response_headers: The response headers.
        :param logger: The logger object.
        :param internal_logger: The internal logger object.
        :param access_token: The access token.
        :param extra_context_to_return: The extra context to return.
        :param resource: The resource type.
        :param id_: The ID of the resource.

        :return: An async generator of FhirGetResponse objects.
        """
        if logger:
            logger.error(f"Fhir Receive failed [{response.status}]: {full_url} ")
        if internal_logger:
            internal_logger.error(
                f"Fhir Receive failed [{response.status}]: {full_url} "
            )
        error_text: str = await response.get_text_async()
        if logger:
            logger.error(error_text)
        if internal_logger:
            internal_logger.error(error_text)
        yield FhirGetResponseFactory.create(
            request_id=request_id,
            url=full_url,
            response_text=error_text,
            access_token=access_token,
            error=error_text,
            total_count=0,
            status=response.status,
            extra_context_to_return=extra_context_to_return,
            resource_type=resource,
            id_=id_,
            response_headers=response_headers,
            results_by_url=response.results_by_url,
            storage_mode=storage_mode,
            create_operation_outcome_for_error=create_operation_outcome_for_error,
        )

    @staticmethod
    async def _handle_response_404(
        *,
        full_url: str,
        request_id: Optional[str],
        response: RetryableAioHttpResponse,
        response_headers: List[str],
        access_token: Optional[str],
        extra_context_to_return: Optional[Dict[str, Any]],
        resource: Optional[str],
        id_: Optional[Union[List[str], str]],
        logger: Optional[Logger],
        storage_mode: CompressedDictStorageMode,
        create_operation_outcome_for_error: Optional[bool],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        This method is responsible for handling a 404 response from the FHIR server.
        A 404 response indicates that the resource was not found.

        :param full_url: The full URL of the request.
        :param request_id: The request ID.
        :param response: The response object from the FHIR server.
        :param response_headers: The response headers.
        :param access_token: The access token.
        :param extra_context_to_return: The extra context to return.
        :param resource: The resource type.
        :param id_: The ID of the resource.

        :return: An async generator of FhirGetResponse objects.
        """
        last_response_text = await response.get_text_async()
        if logger:
            logger.error(f"resource not found! {full_url}")
        yield FhirGetResponseFactory.create(
            request_id=request_id,
            url=full_url,
            response_text=last_response_text,
            error="NotFound",
            access_token=access_token,
            total_count=0,
            status=response.status,
            extra_context_to_return=extra_context_to_return,
            resource_type=resource,
            id_=id_,
            response_headers=response_headers,
            results_by_url=response.results_by_url,
            storage_mode=storage_mode,
            create_operation_outcome_for_error=create_operation_outcome_for_error,
        )

    @staticmethod
    async def _handle_response_200(
        *,
        access_token: Optional[str],
        full_url: str,
        response: RetryableAioHttpResponse,
        request_id: Optional[str],
        response_headers: List[str],
        resources_json: str,
        fn_handle_streaming_chunk: HandleStreamingChunkFunction | None,
        use_data_streaming: bool,
        chunk_size: int,
        extra_context_to_return: Optional[Dict[str, Any]],
        resource: Optional[str],
        id_: Optional[Union[List[str], str]],
        logger: Optional[Logger],
        expand_fhir_bundle: bool,
        separate_bundle_resources: bool,
        url: Optional[str],
        storage_mode: CompressedDictStorageMode,
        create_operation_outcome_for_error: Optional[bool],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        This method is responsible for handling a 200 response from the FHIR server. A 200 response indicates that the
        request was successful.

        :param access_token: The access token.
        :param full_url: The full URL of the request.
        :param response: The response object from the FHIR server.
        :param request_id: The request ID.
        :param response_headers: The response headers.
        :param resources_json: The resources in JSON format.
        :param use_data_streaming: Whether to use data streaming.
        :param chunk_size: The chunk size.
        :param extra_context_to_return: The extra context to return.
        :param resource: The resource type.
        :param id_: The ID of the resource.
        :param logger: The logger object.
        :param expand_fhir_bundle: Whether to expand the FHIR bundle.
        :param separate_bundle_resources: Whether to separate the bundle resources.
        :param url: The URL.

        :return: An async generator of FhirGetResponse objects.
        """
        total_count: int = 0
        next_url: Optional[str] = None
        if use_data_streaming:
            # used to parse the ndjson response for streaming
            nd_json_chunk_streaming_parser: NdJsonChunkStreamingParser = (
                NdJsonChunkStreamingParser()
            )
            async for r in FhirResponseProcessor._handle_response_200_streaming(
                access_token=access_token,
                fn_handle_streaming_chunk=fn_handle_streaming_chunk,
                full_url=full_url,
                nd_json_chunk_streaming_parser=nd_json_chunk_streaming_parser,
                next_url=next_url,
                request_id=request_id,
                response_headers=response_headers,
                total_count=total_count,
                response=response,
                chunk_size=chunk_size,
                extra_context_to_return=extra_context_to_return,
                resource=resource,
                id_=id_,
                logger=logger,
                separate_bundle_resources=separate_bundle_resources,
                expand_fhir_bundle=expand_fhir_bundle,
                url=url,
                storage_mode=storage_mode,
                create_operation_outcome_for_error=create_operation_outcome_for_error,
            ):
                yield r
        else:
            async for r in FhirResponseProcessor._handle_response_200_non_streaming(
                full_url=full_url,
                response=response,
                request_id=request_id,
                access_token=access_token,
                response_headers=response_headers,
                next_url=next_url,
                total_count=total_count,
                resources_json=resources_json,
                extra_context_to_return=extra_context_to_return,
                resource=resource,
                logger=logger,
                id_=id_,
                separate_bundle_resources=separate_bundle_resources,
                expand_fhir_bundle=expand_fhir_bundle,
                url=url,
                storage_mode=storage_mode,
                create_operation_outcome_for_error=create_operation_outcome_for_error,
            ):
                yield r

    @staticmethod
    async def _handle_response_200_non_streaming(
        *,
        full_url: str,
        response: RetryableAioHttpResponse,
        request_id: Optional[str],
        access_token: Optional[str],
        response_headers: List[str],
        resources_json: str,
        next_url: Optional[str],
        total_count: int,
        logger: Optional[Logger],
        expand_fhir_bundle: bool,
        separate_bundle_resources: bool,
        extra_context_to_return: Optional[Dict[str, Any]],
        resource: Optional[str],
        id_: Optional[Union[List[str], str]],
        url: Optional[str],
        storage_mode: CompressedDictStorageMode,
        create_operation_outcome_for_error: Optional[bool],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        This method is responsible for handling a 200 response from the FHIR server. A 200 response indicates that the
        request was successful.  It handles when data streaming is not used.

        :param full_url: The full URL of the request.
        :param response: The response object from the FHIR server.
        :param request_id: The request ID.
        :param access_token: The access token.
        :param response_headers: The response headers.
        :param resources_json: The resources in JSON format.
        :param next_url: The next URL.
        :param total_count: The total count.
        :param logger: The logger object.
        :param expand_fhir_bundle: Whether to expand the FHIR bundle.
        :param separate_bundle_resources: Whether to separate the bundle resources.
        :param extra_context_to_return: The extra context to return.
        :param resource: The resource type.
        :param id_: The ID of the resource.
        :param url: The URL.

        :return: An async generator of FhirGetResponse objects.
        """
        if logger:
            logger.debug(f"Successfully retrieved: {full_url}")
        text: Optional[str] = None
        # noinspection PyBroadException
        try:
            text = await response.get_text_async()
            if len(text) > 0:
                response_json: Dict[str, Any] = json.loads(text)
                if (
                    "resourceType" in response_json
                    and response_json["resourceType"] == "Bundle"
                ):
                    # get next url if present
                    if "link" in response_json:
                        links: List[Dict[str, Any]] = response_json.get("link", [])
                        next_links = [
                            link for link in links if link.get("relation") == "next"
                        ]
                        if len(next_links) > 0:
                            next_link: Dict[str, Any] = next_links[0]
                            next_url = next_link.get("url")

                resources_json, total_count = (
                    await FhirResponseProcessor.expand_or_separate_bundle_async(
                        access_token=access_token,
                        expand_fhir_bundle=expand_fhir_bundle,
                        extra_context_to_return=extra_context_to_return,
                        resource_or_bundle=response_json,
                        separate_bundle_resources=separate_bundle_resources,
                        total_count=total_count,
                        url=url,
                    )
                )
            yield FhirGetResponseFactory.create(
                request_id=request_id,
                url=full_url,
                response_text=resources_json,
                error=None,
                access_token=access_token,
                total_count=total_count,
                status=response.status,
                next_url=next_url,
                extra_context_to_return=extra_context_to_return,
                resource_type=resource,
                id_=id_,
                response_headers=response_headers,
                results_by_url=response.results_by_url,
                storage_mode=storage_mode,
                create_operation_outcome_for_error=create_operation_outcome_for_error,
            )
        except Exception as e:
            if logger:
                logger.error(
                    f"Error processing response from {full_url} with error: {str(e)}"
                )
            yield FhirGetResponseFactory.create(
                request_id=request_id,
                url=full_url,
                response_text=text or "",
                error=str(e),
                access_token=access_token,
                total_count=total_count,
                status=response.status,
                next_url=next_url,
                extra_context_to_return=extra_context_to_return,
                resource_type=resource,
                id_=id_,
                response_headers=response_headers,
                results_by_url=response.results_by_url,
                storage_mode=storage_mode,
                create_operation_outcome_for_error=create_operation_outcome_for_error,
            )

    @staticmethod
    async def expand_or_separate_bundle_async(
        *,
        access_token: Optional[str],
        expand_fhir_bundle: Optional[bool],
        extra_context_to_return: Optional[Dict[str, Any]],
        resource_or_bundle: Dict[str, Any],
        separate_bundle_resources: bool,
        total_count: int,
        url: Optional[str],
    ) -> Tuple[str, int]:

        # see if this is a Resource Bundle and un-bundle it
        if (
            expand_fhir_bundle
            and "resourceType" in resource_or_bundle
            and resource_or_bundle["resourceType"] == "Bundle"
        ):
            bundle_expander_result: BundleExpanderResult = (
                await BundleExpander.expand_bundle_async(
                    total_count=total_count,
                    bundle=resource_or_bundle,
                )
            )
            resources = bundle_expander_result.resources
            total_count = bundle_expander_result.total_count
        else:
            resources = [resource_or_bundle]
            total_count = 1

        if separate_bundle_resources:
            resource_separator_result: ResourceSeparatorResult = (
                await ResourceSeparator.separate_contained_resources_async(
                    resources=resources,
                    access_token=access_token,
                    url=url,
                    extra_context_to_return=extra_context_to_return,
                )
            )
            resources_json = json.dumps(resource_separator_result.resources_dicts)
            total_count = resource_separator_result.total_count
        elif len(resources) > 0:
            total_count = len(resources)
            if len(resources) == 1:
                resources_json = json.dumps(resources[0])
            else:
                resources_json = json.dumps(resources)
        else:
            resources_json = json.dumps(resources)

        return resources_json, total_count

    @staticmethod
    async def _handle_response_200_streaming(
        *,
        access_token: Optional[str],
        fn_handle_streaming_chunk: HandleStreamingChunkFunction | None,
        full_url: str,
        nd_json_chunk_streaming_parser: NdJsonChunkStreamingParser,
        next_url: Optional[str],
        request_id: Optional[str],
        response: RetryableAioHttpResponse,
        response_headers: List[str],
        total_count: int,
        chunk_size: int,
        extra_context_to_return: Optional[Dict[str, Any]],
        resource: Optional[str],
        id_: Optional[Union[List[str], str]],
        logger: Optional[Logger],
        expand_fhir_bundle: bool,
        separate_bundle_resources: bool,
        url: Optional[str],
        storage_mode: CompressedDictStorageMode,
        create_operation_outcome_for_error: Optional[bool],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        This method is responsible for handling a 200 response from the FHIR server. A 200 response indicates that the
        request was successful.  It handles when data streaming is used.

        :param access_token: The access token.
        :param full_url: The full URL of the request.
        :param nd_json_chunk_streaming_parser: The ND JSON chunk streaming parser.
        :param next_url: The next URL.
        :param request_id: The request ID.
        :param response: The response object from the FHIR server.
        :param response_headers: The response headers.
        :param total_count: The total count.
        :param chunk_size: The chunk size.
        :param extra_context_to_return: The extra context to return.
        :param resource: The resource type.
        :param id_: The ID of the resource.
        :param logger: The logger object.

        :return: An async generator of FhirGetResponse objects.

        """
        chunk_number = 0
        chunk_bytes: bytes

        async def get_iter_chunk_iterator() -> AsyncGenerator[bytes, None]:
            """
            Reads the aiohttp response content async generator but returns only the chunked bytes

            """
            if response.content is None:
                return
            async for chunk1, end_of_http_chunk in response.content.iter_chunks():
                yield chunk1

        def get_chunk_iterator() -> (
            AsyncStreamIterator[bytes] | AsyncGenerator[bytes, None]
        ):
            """
            Looks at the headers to determine if the response is chunked or not.  Then returns
            the appropriate async generator

            """
            # for Transfer-Encoding: chunked, we can't use response.content.iter_chunked()
            if response.response_headers.get("Transfer-Encoding") == "chunked":
                return get_iter_chunk_iterator()
            elif response.content is not None:
                return response.content.iter_chunked(chunk_size)
            else:
                raise StopIteration

        total_resources: int = 0
        total_kilobytes: int = 0
        start_time: float = time.time()
        chunk: Optional[str] = None
        try:
            # Check if the response content is empty or the stream has reached the end. If either condition is true,
            # yield a FhirGetResponse indicating no content was received from the request.
            if response.content is None or response.content.at_eof():
                yield FhirGetErrorResponse(
                    request_id=request_id,
                    url=full_url,
                    response_text="",
                    error="No content",
                    access_token=access_token,
                    total_count=0,
                    status=response.status,
                    next_url=next_url,
                    extra_context_to_return=extra_context_to_return,
                    resource_type=resource,
                    id_=id_,
                    response_headers=response_headers,
                    results_by_url=response.results_by_url,
                    storage_mode=storage_mode,
                    create_operation_outcome_for_error=False,
                )
            else:
                # iterate over the chunks and return the completed resources as we get them
                async for chunk_bytes in get_chunk_iterator():
                    # # https://stackoverflow.com/questions/56346811/response-payload-is-not-completed-using-asyncio-aiohttp
                    # await asyncio.sleep(0)
                    chunk_number += 1
                    if fn_handle_streaming_chunk:
                        await fn_handle_streaming_chunk(chunk_bytes, chunk_number)
                    chunk = chunk_bytes.decode("utf-8")
                    chunk_length = len(chunk_bytes)
                    total_kilobytes += chunk_length // 1024
                    completed_resources: List[Dict[str, Any]] = (
                        nd_json_chunk_streaming_parser.add_chunk(
                            chunk=chunk,
                            logger=logger,
                        )
                    )
                    if completed_resources:
                        total_time: float = time.time() - start_time
                        if total_time == 0:
                            total_time = 0.1  # avoid division by zero
                        total_resources += len(completed_resources)
                        total_time_str: str = datetime.fromtimestamp(
                            total_time
                        ).strftime("%H:%M:%S")
                        if logger:
                            logger.debug(
                                f"Chunk: {chunk_number:,}"
                                + f" | Resources: {len(completed_resources):,}"
                                + f" | Total Resources: {total_resources:,}"
                                + f" | Resources/sec: {(total_resources / total_time):,.2f}"
                                + f" | Chunk KB: {chunk_length / 1024:,}"
                                + f" | Total KB: {total_kilobytes:,}"
                                + f" | KB/sec: {(total_kilobytes / total_time):,.2f}"
                                + f" | Url: {full_url}"
                                + f" | Total time: {total_time_str}"
                            )

                        for completed_resource in completed_resources:
                            if expand_fhir_bundle or separate_bundle_resources:
                                resources_json, total_count = (
                                    await FhirResponseProcessor.expand_or_separate_bundle_async(
                                        access_token=access_token,
                                        expand_fhir_bundle=expand_fhir_bundle,
                                        extra_context_to_return=extra_context_to_return,
                                        resource_or_bundle=completed_resource,
                                        separate_bundle_resources=separate_bundle_resources,
                                        total_count=total_count,
                                        url=url,
                                    )
                                )
                            else:
                                resources_json = json.dumps(completed_resource)

                            yield FhirGetResponseFactory.create(
                                request_id=request_id,
                                url=full_url,
                                response_text=resources_json,
                                # responses=(
                                #     json.dumps(completed_resources[0])
                                #     if len(completed_resources) == 1
                                #     else json.dumps(completed_resources)
                                # ),
                                error=None,
                                access_token=access_token,
                                total_count=total_count,
                                status=response.status,
                                next_url=next_url,
                                extra_context_to_return=extra_context_to_return,
                                resource_type=resource,
                                id_=id_,
                                response_headers=response_headers,
                                chunk_number=chunk_number,
                                results_by_url=response.results_by_url,
                                storage_mode=storage_mode,
                                create_operation_outcome_for_error=create_operation_outcome_for_error,
                            )
        except Exception as e:
            if logger:
                logger.error(
                    f"Error processing response from {full_url} with error: {str(e)}"
                )
            yield FhirGetResponseFactory.create(
                request_id=request_id,
                url=full_url,
                response_text=chunk or "",
                error=str(e),
                access_token=access_token,
                total_count=total_count,
                status=response.status,
                next_url=next_url,
                extra_context_to_return=extra_context_to_return,
                resource_type=resource,
                id_=id_,
                response_headers=response_headers,
                results_by_url=response.results_by_url,
                storage_mode=storage_mode,
                create_operation_outcome_for_error=create_operation_outcome_for_error,
            )

    @staticmethod
    async def log_response(
        *,
        full_url: str,
        response_status: int,
        client_id: Optional[str],
        auth_scopes: List[str] | None,
        uuid: UUID,
        logger: Optional[Logger],
        internal_logger: Optional[Logger],
        log_level: Optional[str],
    ) -> None:
        """
        This method is responsible for logging the response from the FHIR server.

        :param full_url: The full URL of the request.
        :param response_status: The response status.
        :param client_id: The client ID.
        :param auth_scopes: The authorization scopes.
        :param uuid: The UUID.
        :param logger: The logger object.
        :param internal_logger: The internal logger object.
        :param log_level: The log level

        :return: None
        """
        if log_level == "DEBUG":
            if logger:
                logger.info(
                    f"response from get_with_session_async: {full_url} status_code {response_status} "
                    + f"with client_id={client_id} and scopes={auth_scopes} "
                    + f"instance_id={uuid} "
                )
            if internal_logger:
                internal_logger.info(
                    f"response from get_with_session_async: {full_url} status_code {response_status} "
                    + f"with client_id={client_id} and scopes={auth_scopes} "
                    + f"instance_id={uuid} "
                )

    @staticmethod
    async def log_request(
        *,
        full_url: str,
        client_id: Optional[str],
        auth_scopes: List[str] | None,
        uuid: UUID,
        logger: Optional[Logger],
        internal_logger: Optional[Logger],
        log_level: Optional[str],
    ) -> None:
        """
        This method is responsible for logging the request to the FHIR server.

        :param full_url: The full URL of the request.
        :param client_id: The client ID.
        :param auth_scopes: The authorization scopes.
        :param uuid: The UUID.
        :param logger: The logger object.
        :param internal_logger: The internal logger object.
        :param log_level: The log level

        :return: None
        """
        if log_level == "DEBUG":
            if logger:
                logger.debug(
                    f"sending a get_with_session_async: {full_url} with client_id={client_id} "
                    + f"and scopes={auth_scopes} instance_id={uuid}"
                )
            if internal_logger:
                internal_logger.info(
                    f"sending a get_with_session_async: {full_url} with client_id={client_id} "
                    + f"and scopes={auth_scopes} instance_id={uuid}"
                )
