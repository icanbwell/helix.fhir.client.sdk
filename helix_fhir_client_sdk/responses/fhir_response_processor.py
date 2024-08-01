import json
import time
from datetime import datetime
from logging import Logger
from typing import Optional, List, Dict, Any, Union, AsyncGenerator, Tuple
from uuid import UUID

from aiohttp import ClientResponse, ClientPayloadError

from helix_fhir_client_sdk.function_types import (
    RefreshTokenFunction,
    HandleStreamingChunkFunction,
)
from helix_fhir_client_sdk.loggers.fhir_logger import FhirLogger
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.utilities.ndjson_chunk_streaming_parser import (
    NdJsonChunkStreamingParser,
)


class FhirResponseProcessor:
    @staticmethod
    async def get_safe_response_text_async(response: Optional[ClientResponse]) -> str:
        try:
            return (
                await response.text() if (response and response.status != 504) else ""
            )
        except Exception as e:
            return str(e)

    @staticmethod
    async def handle_response(
        *,
        response: ClientResponse,
        full_url: str,
        request_id: Optional[str],
        response_headers: List[str],
        access_token: Optional[str],
        retries_left: int,
        resources_json: str,
        fn_handle_streaming_chunk: HandleStreamingChunkFunction | None,
        logger: Optional[FhirLogger] = None,
        internal_logger: Optional[Logger] = None,
        extra_context_to_return: Optional[Dict[str, Any]] = None,
        resource: Optional[str] = None,
        id_: Optional[Union[List[str], str]] = None,
        exclude_status_codes_from_retry: Optional[List[int]] = None,
        refresh_token_function: RefreshTokenFunction,
        auth_server_url: Optional[str],
        auth_scopes: List[str] | None,
        login_token: Optional[str],
        chunk_size: int,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        # if request is ok (200) then return the data
        if response.status == 200:
            async for r in FhirResponseProcessor._handle_response_200(
                full_url=full_url,
                request_id=request_id,
                response=response,
                response_headers=response_headers,
                fn_handle_streaming_chunk=fn_handle_streaming_chunk,
                access_token=access_token,
                retries_left=retries_left,
                resources_json=resources_json,
                resource=resource,
                id_=id_,
                logger=logger,
                use_data_streaming=True,
                chunk_size=chunk_size,
                extra_context_to_return=extra_context_to_return,
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
        elif response.status == 502 or response.status == 504:  # time out
            last_response_text = (
                await FhirResponseProcessor.get_safe_response_text_async(
                    response=response
                )
            )
            if retries_left > 0 and (
                not exclude_status_codes_from_retry
                or response.status not in exclude_status_codes_from_retry
            ):
                pass
        elif response.status == 403:  # forbidden
            async for r in FhirResponseProcessor._handle_response_403(
                full_url=full_url,
                request_id=request_id,
                response=response,
                response_headers=response_headers,
                access_token=access_token,
                id_=id_,
                resource=resource,
                extra_context_to_return=extra_context_to_return,
            ):
                yield r
        elif response.status == 401:  # unauthorized
            async for r in FhirResponseProcessor._handle_response_401(
                full_url=full_url,
                response=response,
                retries_left=retries_left,
                request_id=request_id,
                response_headers=response_headers,
                resource=resource,
                extra_context_to_return=extra_context_to_return,
                access_token=access_token,
                id_=id_,
                login_token=login_token,
                auth_server_url=auth_server_url,
                refresh_token_function=refresh_token_function,
                auth_scopes=auth_scopes,
                exclude_status_codes_from_retry=exclude_status_codes_from_retry,
            ):
                yield r
        elif response.status == 429:  # too many calls
            async for r in FhirResponseProcessor._handle_response_429(
                response=response,
                full_url=full_url,
                request_id=request_id,
                response_headers=response_headers,
                exclude_status_codes_from_retry=exclude_status_codes_from_retry,
                extra_context_to_return=extra_context_to_return,
                access_token=access_token,
                id_=id_,
                resource=resource,
                logger=logger,
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
        response: ClientResponse,
        response_headers: List[str],
        logger: Optional[FhirLogger] = None,
        internal_logger: Optional[Logger] = None,
        access_token: Optional[str],
        extra_context_to_return: Optional[Dict[str, Any]],
        resource: Optional[str],
        id_: Optional[Union[List[str], str]],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        # some unexpected error
        if logger:
            logger.error(f"Fhir Receive failed [{response.status}]: {full_url} ")
        if internal_logger:
            internal_logger.error(
                f"Fhir Receive failed [{response.status}]: {full_url} "
            )
        error_text: str = await FhirResponseProcessor.get_safe_response_text_async(
            response=response
        )
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
    async def _handle_response_429(
        *,
        response: ClientResponse,
        full_url: str,
        request_id: Optional[str],
        response_headers: List[str],
        exclude_status_codes_from_retry: Optional[List[int]],
        access_token: Optional[str],
        extra_context_to_return: Optional[Dict[str, Any]],
        resource: Optional[str],
        id_: Optional[Union[List[str], str]],
        logger: Optional[FhirLogger] = None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        last_response_text = await FhirResponseProcessor.get_safe_response_text_async(
            response=response
        )
        if (
            not exclude_status_codes_from_retry
            or response.status not in exclude_status_codes_from_retry
        ):
            yield FhirGetResponse(
                request_id=request_id,
                url=full_url,
                responses=last_response_text,
                error=None,
                access_token=access_token,
                total_count=0,
                status=response.status,
                extra_context_to_return=extra_context_to_return,
                resource_type=resource,
                id_=id_,
                response_headers=response_headers,
            )
        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/429
        # read the Retry-After header
        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Retry-After
        retry_after_text: str = str(response.headers.getone("Retry-After"))
        if logger:
            logger.info(
                f"Server {full_url} sent a 429 with retry-after: {retry_after_text}"
            )
        if retry_after_text:
            if retry_after_text.isnumeric():  # it is number of seconds
                time.sleep(int(retry_after_text))
            else:
                wait_till: datetime = datetime.strptime(
                    retry_after_text, "%a, %d %b %Y %H:%M:%S GMT"
                )
                while datetime.utcnow() < wait_till:
                    time.sleep(10)
        else:
            time.sleep(60)
        if logger:
            logger.info(
                f"Finished waiting after a 429 with retry-after: {retry_after_text}"
            )

    @staticmethod
    async def _handle_response_401(
        *,
        full_url: str,
        response: ClientResponse,
        retries_left: int,
        request_id: Optional[str],
        response_headers: List[str],
        exclude_status_codes_from_retry: Optional[List[int]],
        access_token: Optional[str],
        extra_context_to_return: Optional[Dict[str, Any]],
        resource: Optional[str],
        id_: Optional[Union[List[str], str]],
        refresh_token_function: RefreshTokenFunction,
        auth_server_url: Optional[str],
        auth_scopes: List[str] | None,
        login_token: Optional[str],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        last_response_text = await FhirResponseProcessor.get_safe_response_text_async(
            response=response
        )
        if retries_left > 0 and (
            not exclude_status_codes_from_retry
            or response.status not in exclude_status_codes_from_retry
        ):
            current_access_token: Optional[str] = access_token
            try:
                access_token = await refresh_token_function(
                    auth_server_url=auth_server_url,
                    auth_scopes=auth_scopes,
                    login_token=login_token,
                )
                if not access_token:
                    # no ability to refresh auth token
                    yield FhirGetResponse(
                        request_id=request_id,
                        url=full_url,
                        responses="",
                        error=last_response_text or "UnAuthorized",
                        access_token=current_access_token,
                        total_count=0,
                        status=response.status,
                        extra_context_to_return=extra_context_to_return,
                        resource_type=resource,
                        id_=id_,
                        response_headers=response_headers,
                    )
            except Exception as ex:
                # no ability to refresh auth token
                yield FhirGetResponse(
                    request_id=request_id,
                    url=full_url,
                    responses="",
                    error=str(ex),
                    access_token=current_access_token,
                    total_count=0,
                    status=response.status,
                    extra_context_to_return=extra_context_to_return,
                    resource_type=resource,
                    id_=id_,
                    response_headers=response_headers,
                )
            # try again
        else:
            # out of retries_left so just fail now
            yield FhirGetResponse(
                request_id=request_id,
                url=full_url,
                responses=await response.text(),
                error=last_response_text or "UnAuthorized",
                access_token=access_token,
                total_count=0,
                status=response.status,
                extra_context_to_return=extra_context_to_return,
                resource_type=resource,
                id_=id_,
                response_headers=response_headers,
            )

    @staticmethod
    async def _handle_response_403(
        *,
        full_url: str,
        request_id: Optional[str],
        response: ClientResponse,
        response_headers: List[str],
        access_token: Optional[str],
        extra_context_to_return: Optional[Dict[str, Any]],
        resource: Optional[str],
        id_: Optional[Union[List[str], str]],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        last_response_text = await FhirResponseProcessor.get_safe_response_text_async(
            response=response
        )
        yield FhirGetResponse(
            request_id=request_id,
            url=full_url,
            responses=last_response_text,
            error=None,
            access_token=access_token,
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
        response: ClientResponse,
        response_headers: List[str],
        access_token: Optional[str],
        extra_context_to_return: Optional[Dict[str, Any]],
        resource: Optional[str],
        id_: Optional[Union[List[str], str]],
        logger: Optional[FhirLogger] = None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        last_response_text = await FhirResponseProcessor.get_safe_response_text_async(
            response=response
        )
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
        response: ClientResponse,
        retries_left: int,
        request_id: Optional[str],
        response_headers: List[str],
        resources_json: str,
        fn_handle_streaming_chunk: HandleStreamingChunkFunction | None,
        use_data_streaming: bool,
        chunk_size: int,
        extra_context_to_return: Optional[Dict[str, Any]],
        resource: Optional[str],
        id_: Optional[Union[List[str], str]],
        logger: Optional[FhirLogger] = None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
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
                retries_left=retries_left,
                next_url=next_url,
                total_count=total_count,
                resources_json=resources_json,
            ):
                yield r

    @staticmethod
    async def _handle_response_200_non_streaming(
        *,
        full_url: str,
        response: ClientResponse,
        retries_left: int,
        request_id: Optional[str],
        access_token: Optional[str],
        response_headers: List[str],
        resources_json: str,
        next_url: Optional[str],
        total_count: int,
        logger: Optional[FhirLogger] = None,
        expand_fhir_bundle: bool = False,
        separate_bundle_resources: bool = False,
        extra_context_to_return: Optional[Dict[str, Any]] = None,
        resource: Optional[str] = None,
        id_: Optional[Union[List[str], str]] = None,
        url: Optional[str] = None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        if logger:
            logger.debug(f"Successfully retrieved: {full_url}")
        # noinspection PyBroadException
        try:
            text = await response.text()
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
                logger.error(
                    f"{e}: {full_url}: retries_left={retries_left} headers={response.headers}"
                )

    @staticmethod
    async def _handle_response_200_streaming(
        *,
        access_token: Optional[str],
        fn_handle_streaming_chunk: HandleStreamingChunkFunction | None,
        full_url: str,
        nd_json_chunk_streaming_parser: NdJsonChunkStreamingParser,
        next_url: Optional[str],
        request_id: Optional[str],
        response: ClientResponse,
        response_headers: List[str],
        total_count: int,
        chunk_size: int,
        extra_context_to_return: Optional[Dict[str, Any]],
        resource: Optional[str],
        id_: Optional[Union[List[str], str]],
        logger: Optional[FhirLogger] = None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        chunk_number = 0
        chunk_bytes: bytes
        async for chunk_bytes in response.content.iter_chunked(chunk_size):
            # # https://stackoverflow.com/questions/56346811/response-payload-is-not-completed-using-asyncio-aiohttp
            # await asyncio.sleep(0)
            chunk_number += 1
            if fn_handle_streaming_chunk:
                await fn_handle_streaming_chunk(chunk_bytes, chunk_number)
            completed_resources: List[Dict[str, Any]] = (
                nd_json_chunk_streaming_parser.add_chunk(
                    chunk=chunk_bytes.decode("utf-8")
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
                logger.debug(f"Successfully retrieved chunk {chunk_number}: {full_url}")

    @staticmethod
    async def log_response(
        *,
        full_url: str,
        response_status: int,
        retries_left: int,
        client_id: Optional[str],
        auth_scopes: List[str] | None,
        uuid: UUID,
        logger: Optional[FhirLogger] = None,
        internal_logger: Optional[Logger] = None,
        log_level: Optional[str],
    ) -> None:
        if log_level == "DEBUG":
            if logger:
                logger.info(
                    f"response from get_with_session_async: {full_url} status_code {response_status} "
                    + f"with client_id={client_id} and scopes={auth_scopes} "
                    + f"instance_id={uuid} "
                    + f"retries_left={retries_left}"
                )
            if internal_logger:
                internal_logger.info(
                    f"response from get_with_session_async: {full_url} status_code {response_status} "
                    + f"with client_id={client_id} and scopes={auth_scopes} "
                    + f"instance_id={uuid} "
                    + f"retries_left={retries_left}"
                )

    @staticmethod
    async def log_request(
        *,
        full_url: str,
        retries_left: int,
        client_id: Optional[str],
        auth_scopes: List[str] | None,
        uuid: UUID,
        logger: Optional[FhirLogger] = None,
        internal_logger: Optional[Logger] = None,
        log_level: Optional[str],
    ) -> None:
        if log_level == "DEBUG":
            if logger:
                logger.debug(
                    f"sending a get_with_session_async: {full_url} with client_id={client_id} "
                    + f"and scopes={auth_scopes} instance_id={uuid} retries_left={retries_left}"
                )
            if internal_logger:
                internal_logger.info(
                    f"sending a get_with_session_async: {full_url} with client_id={client_id} "
                    + f"and scopes={auth_scopes} instance_id={uuid} retries_left={retries_left}"
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
    ) -> Tuple[str, int]:
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
        extra_context_to_return: Optional[Dict[str, Any]] = None,
    ) -> None:
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
