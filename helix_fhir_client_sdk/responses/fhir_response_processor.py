import json
from logging import Logger
from typing import Optional, List, Dict, Any, Union, AsyncGenerator, Tuple
from uuid import UUID

from aiohttp import ClientResponse, ClientPayloadError
from aiohttp.streams import AsyncStreamIterator

from helix_fhir_client_sdk.function_types import (
    HandleStreamingChunkFunction,
)
from helix_fhir_client_sdk.loggers.fhir_logger import FhirLogger
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
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
    async def get_safe_response_text_async(
        *, response: Optional[ClientResponse]
    ) -> str:
        """
        This method is responsible for getting the response text from the response object.

        :param response: The response object from the FHIR server.
        """
        try:
            return (
                await response.text() if (response and response.status != 504) else ""
            )
        except Exception as e:
            return str(e)

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
        logger: Optional[FhirLogger],
        internal_logger: Optional[Logger],
        extra_context_to_return: Optional[Dict[str, Any]],
        resource: Optional[str],
        id_: Optional[Union[List[str], str]],
        chunk_size: int,
        expand_fhir_bundle: bool,
        url: Optional[str],
        separate_bundle_resources: bool,
        use_data_streaming: bool,
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
            ):
                yield r

    @staticmethod
    async def _handle_response_unknown(
        *,
        full_url: str,
        request_id: Optional[str],
        response: RetryableAioHttpResponse,
        response_headers: List[str],
        logger: Optional[FhirLogger],
        internal_logger: Optional[Logger],
        access_token: Optional[str],
        extra_context_to_return: Optional[Dict[str, Any]],
        resource: Optional[str],
        id_: Optional[Union[List[str], str]],
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
        yield FhirGetResponse(
            request_id=request_id,
            url=full_url,
            responses=error_text,
            access_token=access_token,
            error=error_text,
            total_count=0,
            status=response.status,
            extra_context_to_return=extra_context_to_return,
            resource_type=resource,
            id_=id_,
            response_headers=response_headers,
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
        logger: Optional[FhirLogger],
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
        yield FhirGetResponse(
            request_id=request_id,
            url=full_url,
            responses=last_response_text,
            error="NotFound",
            access_token=access_token,
            total_count=0,
            status=response.status,
            extra_context_to_return=extra_context_to_return,
            resource_type=resource,
            id_=id_,
            response_headers=response_headers,
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
        logger: Optional[FhirLogger],
        expand_fhir_bundle: bool,
        separate_bundle_resources: bool,
        url: Optional[str],
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
        logger: Optional[FhirLogger],
        expand_fhir_bundle: bool,
        separate_bundle_resources: bool,
        extra_context_to_return: Optional[Dict[str, Any]],
        resource: Optional[str],
        id_: Optional[Union[List[str], str]],
        url: Optional[str],
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

                # see if this is a Resource Bundle and un-bundle it
                if (
                    expand_fhir_bundle
                    and "resourceType" in response_json
                    and response_json["resourceType"] == "Bundle"
                ):
                    (
                        resources_json,
                        total_count,
                    ) = await FhirResponseProcessor._expand_bundle_async(
                        access_token=access_token,
                        total_count=total_count,
                        resources=resources_json,
                        response_json=response_json,
                        url=url or "",
                        separate_bundle_resources=separate_bundle_resources,
                        extra_context_to_return=extra_context_to_return,
                    )
                elif (
                    separate_bundle_resources
                    and "resourceType" in response_json
                    and response_json["resourceType"] != "Bundle"
                ):
                    # single resource was returned
                    resources_dict = {
                        f'{response_json["resourceType"].lower()}': [response_json],
                        "token": access_token,
                        "url": url,
                    }
                    if extra_context_to_return:
                        resources_dict.update(extra_context_to_return)

                    resources_json = json.dumps(resources_dict)
                else:
                    resources_json = text
            yield FhirGetResponse(
                request_id=request_id,
                url=full_url,
                responses=resources_json,
                error=None,
                access_token=access_token,
                total_count=total_count,
                status=response.status,
                next_url=next_url,
                extra_context_to_return=extra_context_to_return,
                resource_type=resource,
                id_=id_,
                response_headers=response_headers,
            )
        except ClientPayloadError as e:
            # do a retry
            if logger:
                logger.error(f"{e}: {full_url}: headers={response.response_headers}")

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
        logger: Optional[FhirLogger],
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
            else:
                return response.content.iter_chunked(chunk_size)

        # iterate over the chunks and return the completed resources as we get them
        async for chunk_bytes in get_chunk_iterator():
            # # https://stackoverflow.com/questions/56346811/response-payload-is-not-completed-using-asyncio-aiohttp
            # await asyncio.sleep(0)
            chunk_number += 1
            if fn_handle_streaming_chunk:
                await fn_handle_streaming_chunk(chunk_bytes, chunk_number)
            chunk = chunk_bytes.decode("utf-8")
            completed_resources: List[Dict[str, Any]] = (
                nd_json_chunk_streaming_parser.add_chunk(
                    chunk=chunk,
                    logger=logger,
                )
            )
            if completed_resources:
                yield FhirGetResponse(
                    request_id=request_id,
                    url=full_url,
                    responses=(
                        json.dumps(completed_resources[0])
                        if len(completed_resources) == 1
                        else json.dumps(completed_resources)
                    ),
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
                )
                if logger:
                    logger.debug(
                        f"Successfully got completed resources from {full_url}:\n{completed_resources}"
                    )
            else:
                if logger:
                    logger.debug(
                        f"No new complete resources from chunk {chunk_number} from {full_url}: \n{chunk}"
                    )

    @staticmethod
    async def log_response(
        *,
        full_url: str,
        response_status: int,
        client_id: Optional[str],
        auth_scopes: List[str] | None,
        uuid: UUID,
        logger: Optional[FhirLogger],
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
        logger: Optional[FhirLogger],
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

    @staticmethod
    async def _expand_bundle_async(
        *,
        resources: str,
        response_json: Dict[str, Any],
        total_count: int,
        access_token: Optional[str],
        url: str,
        separate_bundle_resources: bool,
        extra_context_to_return: Optional[Dict[str, Any]],
    ) -> Tuple[str, int]:
        """
        This method is responsible for expanding the FHIR bundle.

        :param resources: The resources in JSON format.
        :param response_json: The response JSON.
        :param total_count: The total count.
        :param access_token: The access token.
        :param url: The URL.
        :param separate_bundle_resources: Whether to separate the bundle resources.
        :param extra_context_to_return: The extra context to return.

        :return: A tuple of the resources in JSON format and the total count.
        """
        if "total" in response_json:
            total_count = int(response_json["total"])
        if "entry" in response_json:
            entries: List[Dict[str, Any]] = response_json["entry"]
            entry: Dict[str, Any]
            resources_list: List[Dict[str, Any]] = []
            for entry in entries:
                if "resource" in entry:
                    if separate_bundle_resources:
                        await FhirResponseProcessor._separate_contained_resources_async(
                            entry=entry,
                            resources_list=resources_list,
                            access_token=access_token,
                            url=url,
                            extra_context_to_return=extra_context_to_return,
                        )
                    else:
                        resources_list.append(entry["resource"])

            resources = json.dumps(resources_list)
        return resources, total_count

    @staticmethod
    async def _separate_contained_resources_async(
        *,
        entry: Dict[str, Any],
        resources_list: List[Dict[str, Any]],
        access_token: Optional[str],
        url: str,
        extra_context_to_return: Optional[Dict[str, Any]],
    ) -> None:
        """
        This method is responsible for separating the contained resources.

        :param entry: The entry.
        :param resources_list: The resources list.
        :param access_token: The access token.
        :param url: The URL.
        :param extra_context_to_return: The extra context to return.

        :return: None
        """
        # if self._action != "$graph":
        #     raise Exception(
        #         "only $graph action with _separate_bundle_resources=True"
        #         " is supported at this moment"
        #     )
        resources_dict: Dict[str, Union[Optional[str], List[Any]]] = (
            {}
        )  # {resource type: [data]}}
        # iterate through the entry list
        # have to split these here otherwise when Spark loads them
        # it can't handle
        # that items in the entry array can have different schemas
        resource_type: str = str(entry["resource"]["resourceType"]).lower()
        parent_resource: Dict[str, Any] = entry["resource"]
        resources_dict[resource_type] = [parent_resource]
        # $graph returns "contained" if there is any related resources
        if "contained" in entry["resource"]:
            contained = parent_resource.pop("contained")
            for contained_entry in contained:
                resource_type = str(contained_entry["resourceType"]).lower()
                if resource_type not in resources_dict:
                    resources_dict[resource_type] = []

                if isinstance(resources_dict[resource_type], list):
                    resources_dict[resource_type].append(contained_entry)  # type: ignore
        resources_dict["token"] = access_token
        resources_dict["url"] = url
        if extra_context_to_return:
            resources_dict.update(extra_context_to_return)
        resources_list.append(resources_dict)
