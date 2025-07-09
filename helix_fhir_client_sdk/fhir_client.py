from __future__ import annotations

import logging
import ssl
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from logging import Logger
from os import environ
from threading import Lock
from types import SimpleNamespace
from typing import (
    Any,
)
from urllib import parse

import aiohttp
import certifi
from aiohttp import (
    ClientSession,
    TCPConnector,
    TraceRequestEndParams,
    TraceResponseChunkReceivedParams,
)
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from furl import furl
from requests.adapters import BaseAdapter

from helix_fhir_client_sdk.dictionary_writer import convert_dict_to_str
from helix_fhir_client_sdk.fhir_auth_mixin import FhirAuthMixin
from helix_fhir_client_sdk.fhir_delete_mixin import FhirDeleteMixin
from helix_fhir_client_sdk.fhir_merge_mixin import FhirMergeMixin
from helix_fhir_client_sdk.fhir_merge_resources_mixin import FhirMergeResourcesMixin
from helix_fhir_client_sdk.fhir_patch_mixin import FhirPatchMixin
from helix_fhir_client_sdk.fhir_update_mixin import FhirUpdateMixin
from helix_fhir_client_sdk.filters.base_filter import BaseFilter
from helix_fhir_client_sdk.filters.sort_field import SortField
from helix_fhir_client_sdk.function_types import (
    HandleStreamingChunkFunction,
    RefreshTokenFunction,
    TraceRequestFunction,
)
from helix_fhir_client_sdk.graph.fhir_graph_mixin import FhirGraphMixin
from helix_fhir_client_sdk.graph.simulated_graph_processor_mixin import (
    SimulatedGraphProcessorMixin,
)
from helix_fhir_client_sdk.queue.request_queue_mixin import RequestQueueMixin
from helix_fhir_client_sdk.responses.fhir_client_protocol import FhirClientProtocol
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.structures.get_access_token_result import (
    GetAccessTokenResult,
)
from helix_fhir_client_sdk.utilities.async_runner import AsyncRunner
from helix_fhir_client_sdk.utilities.fhir_client_logger import FhirClientLogger


class FhirClient(
    SimulatedGraphProcessorMixin,
    FhirMergeMixin,
    FhirMergeResourcesMixin,
    FhirGraphMixin,
    FhirUpdateMixin,
    FhirPatchMixin,
    FhirAuthMixin,
    FhirDeleteMixin,
    RequestQueueMixin,
    FhirClientProtocol,  # the protocol has to come last
):
    """
    Class used to call FHIR server (uses async and parallel execution to speed up)
    """

    _internal_logger: Logger = logging.getLogger("FhirClient")
    # link handler to logger
    _internal_logger.addHandler(logging.StreamHandler())
    _internal_logger.setLevel(logging.INFO)

    def __init__(self) -> None:
        """
        Class used to call FHIR server (uses async and parallel execution to speed up)
        """
        self._action: str | None = None
        self._action_payload: dict[str, Any] | None = None
        self._resource: str | None = None
        self._id: list[str] | str | None = None
        self._url: str | None = None
        self._additional_parameters: list[str] | None = None
        self._filter_by_resource: str | None = None
        self._filter_parameter: str | None = None
        self._include_only_properties: list[str] | None = None
        self._page_number: int | None = None
        self._page_size: int | None = None
        self._last_updated_after: datetime | None = None
        self._last_updated_before: datetime | None = None
        self._sort_fields: list[SortField] | None = None
        self._logger: Logger | None = None
        self._adapter: BaseAdapter | None = None
        self._limit: int | None = None
        self._validation_server_url: str | None = None
        self._separate_bundle_resources: bool = False  # for each entry in bundle create a property for each resource
        self._obj_id: str | None = None
        self._include_total: bool = False
        self._filters: list[BaseFilter] = []
        self._expand_fhir_bundle: bool = True
        self._smart_merge: bool | None = None

        self._stop_processing: bool = False
        self._last_page: int | None = None

        self._use_data_streaming: bool = False
        self._send_data_as_chunked: bool = False
        self._last_page_lock: Lock = Lock()

        self._use_post_for_search: bool = False

        self._accept: str = "application/fhir+json"
        self._content_type: str = "application/fhir+json"
        self._additional_request_headers: dict[str, str] = {}
        self._accept_encoding: str = "gzip,deflate"

        self._maximum_time_to_retry_on_429: int = 60 * 60

        self._extra_context_to_return: dict[str, Any] | None = None

        self._retry_count: int = 2
        self._exclude_status_codes_from_retry: list[int] | None = None

        self._uuid = uuid.uuid4()
        self._log_level: str | None = environ.get("LOGLEVEL")
        # default to built-in function to refresh token
        self._refresh_token_function: RefreshTokenFunction = self.authenticate_async_wrapper()
        self._trace_request_function: TraceRequestFunction | None = None
        self._chunk_size: int = 1024

        self._compress: bool = True

        self._throw_exception_on_error: bool = True

        FhirAuthMixin.__init__(self)

        RequestQueueMixin.__init__(self)

        self._log_all_response_urls: bool = False
        """ If True, logs all response URLs and status codes.  Can take a lot of memory for when there are many responses. """

        self._storage_mode = CompressedDictStorageMode(storage_type="raw")

        self._create_operation_outcome_for_error = False

    def action(self, action: str) -> FhirClient:
        """
        Set the action

        :param action: (Optional) do an action e.g., $everything
        """
        self._action = action
        return self

    def action_payload(self, action_payload: dict[str, Any]) -> FhirClient:
        """
        Set action payload

        :param action_payload: (Optional) if action such as $graph needs a http payload
        """
        self._action_payload = action_payload
        return self

    def resource(self, resource: str) -> FhirClient:
        """
        set resource to query

        :param resource: what FHIR resource to retrieve
        """
        self._resource = resource
        return self

    def id_(self, id_: list[str] | str | None) -> FhirClient:
        self._id = id_
        return self

    def url(self, url: str) -> FhirClient:
        """
        set url


        :param url: server to call for FHIR
        """
        self._url = url
        return self

    def validation_server_url(self, validation_server_url: str) -> FhirClient:
        """
        set url to validate


        :param validation_server_url: server to call for FHIR validation
        """
        self._validation_server_url = validation_server_url
        return self

    def additional_parameters(self, additional_parameters: list[str]) -> FhirClient:
        """
        set additional parameters


        :param additional_parameters: Any additional parameters to send with request
        """
        self._additional_parameters = additional_parameters
        return self

    def filter_by_resource(self, filter_by_resource: str) -> FhirClient:
        """
        filter


        :param filter_by_resource: filter the resource by this. e.g., /Condition?Patient=1
                (resource=Condition, filter_by_resource=Patient)
        """
        self._filter_by_resource = filter_by_resource
        return self

    def filter_parameter(self, filter_parameter: str) -> FhirClient:
        """
        filter


        :param filter_parameter: Instead of requesting ?patient=1,
                do ?subject:Patient=1 (if filter_parameter is subject)
        """
        self._filter_parameter = filter_parameter
        return self

    def include_only_properties(self, include_only_properties: list[str] | None) -> FhirClient:
        """
        include only these properties


        :param include_only_properties: includes only these properties
        """
        self._include_only_properties = include_only_properties
        return self

    def page_number(self, page_number: int) -> FhirClient:
        """
        page number to load


        :param page_number: page number to load
        """
        self._page_number = page_number
        return self

    def page_size(self, page_size: int) -> FhirClient:
        """
        page size


        :param page_size: (Optional) use paging and get this many items in each page
        """

        self._page_size = page_size
        return self

    def last_updated_after(self, last_updated_after: datetime) -> FhirClient:
        """
        get records updated after this datetime


        :param last_updated_after: (Optional) Only get records newer than this
        """
        self._last_updated_after = last_updated_after
        return self

    def last_updated_before(self, last_updated_before: datetime) -> FhirClient:
        """
        get records updated before this datetime


        :param last_updated_before: (Optional) Only get records older than this
        """
        self._last_updated_before = last_updated_before
        return self

    def sort_fields(self, sort_fields: list[SortField]) -> FhirClient:
        """
        sort


        :param sort_fields: sort by fields in the resource
        """
        self._sort_fields = sort_fields
        return self

    def maximum_time_to_retry_on_429(self, time_in_seconds: int) -> FhirClient:
        self._maximum_time_to_retry_on_429 = time_in_seconds
        return self

    def extra_context_to_return(self, context: dict[str, Any]) -> FhirClient:
        self._extra_context_to_return = context
        return self

    def exclude_status_codes_from_retry(self, status_codes: list[int]) -> FhirClient:
        self._exclude_status_codes_from_retry = status_codes
        return self

    def retry_count(self, count: int) -> FhirClient:
        self._retry_count = count
        return self

    def logger(self, logger: Logger) -> FhirClient:
        """
        Logger to use for logging calls to the FHIR server


        :param logger: logger
        """
        self._logger = logger
        if self._log_level != "DEBUG":
            # disable internal logger
            self._internal_logger.setLevel(logging.ERROR)
        return self

    def adapter(self, adapter: BaseAdapter) -> FhirClient:
        """
        Http Adapter to use for calling the FHIR server


        :param adapter: adapter
        """
        self._adapter = adapter
        return self

    def limit(self, limit: int) -> FhirClient:
        """
        Limit the results


        :param limit: Limit results to this count
        """
        self._limit = limit
        return self

    def use_data_streaming(self, use: bool) -> FhirClient:
        """
        Use data streaming or not


        :param use: where to use data streaming
        """
        self._use_data_streaming = use
        # The b.well FHIR server as of version 5.3.16 has a bug that it cannot parse an accept string with multiple
        # accepts.  We should remove this when that is fixed.
        if use:
            self._accept = "application/fhir+ndjson"

        return self

    def send_data_as_chunked(self, send_data_as_chunked: bool) -> FhirClient:
        """
        Send data as chunked


        :param send_data_as_chunked: whether to send data as chunked
        """
        self._send_data_as_chunked = send_data_as_chunked
        return self

    def use_post_for_search(self, use: bool) -> FhirClient:
        """
        Whether to use POST instead of GET for search


        :param use:
        """
        self._use_post_for_search = use
        return self

    def accept(self, accept_type: str) -> FhirClient:
        """
        Type to send to server in the request header Accept

        :param accept_type:
        :return:
        """
        self._accept = accept_type
        return self

    def content_type(self, type_: str) -> FhirClient:
        """
        Type to send to server in the request header Content-Type

        :param type_:
        :return:
        """
        self._content_type = type_
        return self

    def additional_request_headers(self, headers: dict[str, str]) -> FhirClient:
        """
        Additional headers to send to server in the request header

        :param headers: Request headers dictionary
        :return:
        """
        self._additional_request_headers = headers
        return self

    def accept_encoding(self, encoding: str) -> FhirClient:
        """
        Type to send to server in the request header Accept-Encoding

        :param encoding:
        :return:
        """
        self._accept_encoding = encoding
        return self

    def log_level(self, level: str | None) -> FhirClient:
        self._log_level = level
        return self

    def refresh_token_function(self, fn: RefreshTokenFunction) -> FhirClient:
        """
        Sets the function to call to refresh the token

        :param fn: function to call to refresh the token
        """
        self._refresh_token_function = fn
        return self

    def chunk_size(self, size: int) -> FhirClient:
        """
        Sets the chunk size for streaming

        :param size: size of the chunk
        """
        self._chunk_size = size
        return self

    def last_page(self, last_page: int) -> FhirClient:
        """
        Sets the last page number

        :param last_page: last page number
        """
        self._last_page = last_page
        return self

    def compress(self, compress: bool) -> FhirClient:
        """
        Sets the compress flag

        :param compress: whether to compress the response
        """
        self._compress = compress
        return self

    def throw_exception_on_error(self, throw_exception_on_error: bool) -> FhirClient:
        """
        Sets the throw_exception_on_error flag

        :param throw_exception_on_error: whether to throw an exception on error
        """
        self._throw_exception_on_error = throw_exception_on_error
        return self

    # noinspection PyUnusedLocal
    @staticmethod
    async def on_request_end(
        session: ClientSession,
        trace_config_ctx: SimpleNamespace,
        params: TraceRequestEndParams,
    ) -> None:
        accept: str | None = params.response.request_info.headers.get("Accept", "")
        accept_encoding: str | None = params.response.request_info.headers.get("Accept-Encoding", "")
        content_type_sent: str | None = params.response.request_info.headers.get("Content-Type", "")
        content_encoding_sent: str | None = params.response.request_info.headers.get("Content-Encoding", "")
        transfer_encoding_sent: str | None = params.response.request_info.headers.get("Transfer-Encoding", "")
        FhirClient._internal_logger.info(
            f"Sent: {params.method} {params.url}"
            + f" | Accept: {accept}"
            + f" | Accept-Encoding: {accept_encoding}"
            + f" | Content-Type: {content_type_sent}"
            + f" | Content-Encoding: {content_encoding_sent}"
            + f" | Transfer-Encoding: {transfer_encoding_sent}"
        )
        sent_headers: list[str] = [f"{key}:{value}" for key, value in params.response.request_info.headers.items()]
        FhirClient._internal_logger.debug(f"Sent headers: {sent_headers}")
        received_headers: list[str] = [f"{key}:{value}" for key, value in params.response.headers.items()]
        FhirClient._internal_logger.debug(f"Received headers: {received_headers}")

        # Log that we received a response
        content_type: str | None = params.response.headers.get("Content-Type", "")
        content_encoding: str | None = params.response.headers.get("Content-Encoding", "")
        transfer_encoding: str | None = params.response.headers.get("Transfer-Encoding", "")

        FhirClient._internal_logger.info(
            f"Received: {params.method} {params.url}"
            + f" | Status: {params.response.status}"
            + f" | Content-Type: {content_type}"
            + f" | Transfer-Encoding: {transfer_encoding}"
            + f" | Content-Encoding: {content_encoding}"
        )

    # noinspection PyUnusedLocal
    @staticmethod
    async def on_response_chunk_received(
        session: ClientSession,
        trace_config_ctx: SimpleNamespace,
        params: TraceResponseChunkReceivedParams,
    ) -> None:
        FhirClient._internal_logger.debug(
            f"[CHUNK] {params.method} {params.url} "
            f"Chunk received:\n{params.chunk.decode('utf-8') if params.chunk else '[Empty]'}"
        )

    def get_access_token(self) -> GetAccessTokenResult:
        return AsyncRunner.run(self.get_access_token_async())

    def set_access_token(self, value: str | None) -> FhirClient:
        """
        Sets access token


        :param value: access token
        """
        self._access_token = value
        return self

    def set_access_token_expiry_date(self, value: datetime | None) -> FhirClient:
        """
        Sets access token


        :param value: access token
        """
        self._access_token_expiry_date = value
        return self

    def separate_bundle_resources(self, separate_bundle_resources: bool) -> FhirClient:
        """
        Set flag to separate bundle resources


        :param separate_bundle_resources:
        """
        self._separate_bundle_resources = separate_bundle_resources
        return self

    def expand_fhir_bundle(self, expand_fhir_bundle: bool) -> FhirClient:
        """
        Set flag to expand the FHIR bundle into a list of resources. If false then we don't un bundle the response


        :param expand_fhir_bundle: whether to just return the result as a FHIR bundle
        """
        self._expand_fhir_bundle = expand_fhir_bundle
        return self

    def smart_merge(self, smart_merge: bool | None) -> FhirClient:
        """
        Sets the smartMerge query parameter

        :param smart_merge: whether to enable smartMerge
        """
        self._smart_merge = smart_merge
        return self

    async def get_async(
        self,
        data_chunk_handler: HandleStreamingChunkFunction | None = None,
    ) -> FhirGetResponse:
        """
        Issues a GET call

        :param data_chunk_handler: function to call for each chunk of data

        :return: response
        """
        instance_variables_text = convert_dict_to_str(FhirClientLogger.get_variables_to_log(vars(self)))
        if self._logger:
            # self._logger.info(f"LOGLEVEL: {self._log_level}")
            self._logger.debug(f"parameters: {instance_variables_text}")
        else:
            self._internal_logger.debug(f"LOGLEVEL (InternalLogger): {self._log_level}")
            self._internal_logger.debug(f"parameters: {instance_variables_text}")
        ids: list[str] | None = None
        if self._id:
            ids = self._id if isinstance(self._id, list) else [self._id]
        # actually make the request
        full_response: FhirGetResponse | None = None
        async for response in self._get_with_session_async(
            ids=ids,
            fn_handle_streaming_chunk=data_chunk_handler,
            page_number=None,
            id_above=None,
            additional_parameters=None,
            resource_type=None,
        ):
            if response:
                if full_response:
                    full_response = full_response.append(response)
                else:
                    full_response = response
        assert full_response
        return full_response

    async def get_raw_resources_async(
        self,
    ) -> dict[str, Any]:
        """
        Issues a GET call and returns the raw resources as a list of dictionaries.
        While using this function, the page_size and limit parameters should be equal.

        :return: response
        """
        instance_variables_text = convert_dict_to_str(FhirClientLogger.get_variables_to_log(vars(self)))
        if self._logger:
            # self._logger.info(f"LOGLEVEL: {self._log_level}")
            self._logger.debug(f"parameters: {instance_variables_text}")
        else:
            self._internal_logger.debug(f"LOGLEVEL (InternalLogger): {self._log_level}")
            self._internal_logger.debug(f"parameters: {instance_variables_text}")
        ids: list[str] | None = None
        if self._id:
            ids = self._id if isinstance(self._id, list) else [self._id]
        return await self._get_raw_with_session_async(
            page_number=None,
            ids=ids,
            id_above=None,
            additional_parameters=None,
            resource_type=None,
        )

    async def get_streaming_async(
        self,
        *,
        data_chunk_handler: HandleStreamingChunkFunction | None = None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        Issues a GET call and returns a generator for streaming

        :param data_chunk_handler: function to call for each chunk of data

        :return: async generator of responses
        """
        instance_variables_text = convert_dict_to_str(FhirClientLogger.get_variables_to_log(vars(self)))
        if self._logger:
            # self._logger.info(f"LOGLEVEL: {self._log_level}")
            self._logger.info(f"parameters: {instance_variables_text}")
        else:
            self._internal_logger.info(f"LOGLEVEL (InternalLogger): {self._log_level}")
            self._internal_logger.info(f"parameters: {instance_variables_text}")
        ids: list[str] | None = None
        if self._id:
            ids = self._id if isinstance(self._id, list) else [self._id]
        # actually make the request
        response: FhirGetResponse | None
        async for response in self._get_with_session_async(
            ids=ids,
            fn_handle_streaming_chunk=data_chunk_handler,
            page_number=None,
            id_above=None,
            additional_parameters=None,
            resource_type=None,
        ):
            yield response

    def get(self) -> FhirGetResponse:
        """
        Issues a GET call

        :return: response
        """
        result: FhirGetResponse = AsyncRunner.run(self.get_async())
        return result

    # noinspection PyProtocol
    async def build_url(
        self,
        *,
        additional_parameters: list[str] | None,
        id_above: str | None,
        ids: list[str] | None,
        page_number: int | None,
        resource_type: str | None,
    ) -> str:
        full_uri: furl = furl(self._url)
        full_uri /= resource_type or self._resource
        if self._obj_id:
            full_uri /= parse.quote(str(self._obj_id), safe="")
        if ids is not None and len(ids) > 0:
            if self._filter_by_resource:
                if self._filter_parameter:
                    # ?subject:Patient=27384972
                    full_uri.args[f"{self._filter_parameter}:{self._filter_by_resource}"] = ",".join(sorted(ids))
                else:
                    # ?patient=27384972
                    full_uri.args[self._filter_by_resource.lower()] = ",".join(sorted(ids))
            else:
                if len(ids) == 1 and not self._obj_id:
                    full_uri /= ids
                else:
                    full_uri.args["_id"] = ",".join(sorted(ids))
        # add action to url
        if self._action:
            full_uri /= self._action
        # add a query for just desired properties
        if self._include_only_properties:
            full_uri.args["_elements"] = ",".join(self._include_only_properties)
        if self._page_size and (self._page_number is not None or page_number is not None):
            # noinspection SpellCheckingInspection
            full_uri.args["_count"] = self._page_size
            # noinspection SpellCheckingInspection
            full_uri.args["_getpagesoffset"] = page_number or self._page_number
        # replace _count if page_size is not provided but limit is there, should be used cautiously
        elif not self._obj_id and (ids is None or self._filter_by_resource) and self._limit and self._limit >= 0:
            full_uri.args["_count"] = self._limit
        # add any sort fields
        if self._sort_fields is not None:
            full_uri.args["_sort"] = ",".join([str(s) for s in self._sort_fields])
        # create full url by adding on any query parameters
        full_url: str = full_uri.url
        query_param_exists: bool = True if len(full_uri.args) > 0 else False
        if additional_parameters:
            if query_param_exists:
                full_url += "&"
            else:
                query_param_exists = True
                full_url += "?"
            full_url += "&".join(additional_parameters)
        elif self._additional_parameters:
            if query_param_exists:
                full_url += "&"
            else:
                query_param_exists = True
                full_url += "?"
            full_url += "&".join(self._additional_parameters)
        if self._include_total:
            if query_param_exists:
                full_url += "&"
            else:
                query_param_exists = True
                full_url += "?"
            full_url += "_total=accurate"
        if self._filters and len(self._filters) > 0:
            if query_param_exists:
                full_url += "&"
            else:
                query_param_exists = True
                full_url += "?"
            full_url += "&".join({str(f) for f in self._filters})  # remove any duplicates
        # have to be done here since this arg can be used twice
        if self._last_updated_before:
            if query_param_exists:
                full_url += "&"
            else:
                query_param_exists = True
                full_url += "?"
            full_url += f"_lastUpdated=lt{self._last_updated_before.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        if self._last_updated_after:
            if query_param_exists:
                full_url += "&"
            else:
                query_param_exists = True
                full_url += "?"
            full_url += f"_lastUpdated=ge{self._last_updated_after.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        if id_above is not None:
            if query_param_exists:
                full_url += "&"
            else:
                full_url += "?"
            full_url += f"id:above={id_above}"
        return full_url

    def create_http_session(self) -> ClientSession:
        """
        Creates an HTTP Session

        """
        trace_config = aiohttp.TraceConfig()
        # trace_config.on_request_start.append(on_request_start)
        if self._log_level == "DEBUG":
            trace_config.on_request_end.append(FhirClient.on_request_end)
            trace_config.on_response_chunk_received.append(FhirClient.on_response_chunk_received)
        # https://stackoverflow.com/questions/56346811/response-payload-is-not-completed-using-asyncio-aiohttp
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        timeout = aiohttp.ClientTimeout(total=60 * 60, sock_read=240)
        session: ClientSession = aiohttp.ClientSession(
            connector=TCPConnector(ssl=ssl_context),
            trace_configs=[trace_config],
            headers={"Connection": "keep-alive"},
            timeout=timeout,
        )
        return session

    def include_total(self, include_total: bool) -> FhirClient:
        """
        Whether to ask the server to include the total count in the result


        :param include_total: whether to include total count
        """
        self._include_total = include_total
        return self

    def filter(self, filter_: list[BaseFilter]) -> FhirClient:
        """
        Allows adding in a custom filters that derives from BaseFilter


        :param filter_: list of custom filter instances that derives from BaseFilter.
        """
        assert isinstance(filter_, list), "This function requires a list"
        self._filters.extend(filter_)
        return self

    def clone(self) -> FhirClient:
        """
        Clones the current instance


        :return: cloned instance
        """
        fhir_client = FhirClient()
        fhir_client._url = self._url
        fhir_client._resource = self._resource
        fhir_client._id = self._id
        fhir_client._obj_id = self._obj_id
        fhir_client._action = self._action
        fhir_client._accept = self._accept
        fhir_client._content_type = self._content_type
        fhir_client._accept_encoding = self._accept_encoding
        fhir_client._page_size = self._page_size
        fhir_client._page_number = 0  # reset page number to 1
        fhir_client._limit = self._limit
        fhir_client._sort_fields = self._sort_fields
        fhir_client._filters = self._filters
        fhir_client._last_updated_before = self._last_updated_before
        fhir_client._last_updated_after = self._last_updated_after
        fhir_client._include_only_properties = self._include_only_properties
        fhir_client._include_total = self._include_total
        fhir_client._additional_parameters = self._additional_parameters
        fhir_client._additional_request_headers = self._additional_request_headers
        fhir_client._action_payload = self._action_payload
        fhir_client._logger = self._logger
        fhir_client._internal_logger = self._internal_logger
        fhir_client._log_level = self._log_level
        fhir_client._auth_scopes = self._auth_scopes
        fhir_client._client_id = self._client_id
        fhir_client._auth_server_url = self._auth_server_url
        fhir_client._login_token = self._login_token
        fhir_client._refresh_token_function = self._refresh_token_function
        fhir_client._exclude_status_codes_from_retry = self._exclude_status_codes_from_retry
        fhir_client._chunk_size = self._chunk_size
        fhir_client._expand_fhir_bundle = self._expand_fhir_bundle
        fhir_client._separate_bundle_resources = self._separate_bundle_resources
        fhir_client._use_data_streaming = self._use_data_streaming
        fhir_client._extra_context_to_return = self._extra_context_to_return
        fhir_client._well_known_configuration_cache = self._well_known_configuration_cache
        fhir_client._auth_wellknown_url = self._auth_wellknown_url
        fhir_client._time_to_live_in_secs_for_cache = self._time_to_live_in_secs_for_cache
        fhir_client._validation_server_url = self._validation_server_url
        fhir_client._smart_merge = self._smart_merge
        return fhir_client

    def set_log_all_response_urls(self, value: bool) -> FhirClient:
        """
        Sets the log_all_response_urls flag

        :param value: whether to log all response URLs and status codes
        """
        self._log_all_response_urls = value
        return self

    def set_trace_request_function(self, value: TraceRequestFunction) -> FhirClient:
        """
        Sets the trace_request_function

        :param value: function to trace the request
        """
        self._trace_request_function = value
        return self

    def set_storage_mode(self, value: CompressedDictStorageMode) -> FhirClient:
        """
        Sets the storage mode

        :param value: storage mode
        """
        self._storage_mode = value
        return self

    def set_create_operation_outcome_for_error(self, value: bool) -> FhirClient:
        """
        Sets the create_operation_outcome_for_error flag

        :param value: whether to create operation outcome for error
        """
        self._create_operation_outcome_for_error = value
        return self
