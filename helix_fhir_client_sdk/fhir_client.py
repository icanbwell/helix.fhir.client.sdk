from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
import uuid
from asyncio import Future
from datetime import datetime, timedelta
from logging import Logger
from os import environ
from queue import Empty
from threading import Lock
from types import SimpleNamespace
from typing import (
    Dict,
    Optional,
    List,
    Union,
    Any,
    Generator,
    AsyncGenerator,
    Coroutine,
    Tuple,
)
from urllib import parse

# noinspection PyPackageRequirements
import aiohttp

# noinspection PyPackageRequirements
import requests

# noinspection PyPackageRequirements
from aiohttp import (
    ClientSession,
    ClientResponse,
    ClientPayloadError,
    TraceRequestEndParams,
)

# noinspection PyPackageRequirements
from furl import furl

# noinspection PyPackageRequirements
from requests.adapters import BaseAdapter

from helix_fhir_client_sdk.dictionary_writer import convert_dict_to_str
from helix_fhir_client_sdk.exceptions.fhir_sender_exception import FhirSenderException
from helix_fhir_client_sdk.exceptions.fhir_validation_exception import (
    FhirValidationException,
)
from helix_fhir_client_sdk.filters.base_filter import BaseFilter
from helix_fhir_client_sdk.filters.last_updated_filter import LastUpdatedFilter
from helix_fhir_client_sdk.filters.sort_field import SortField
from helix_fhir_client_sdk.function_types import (
    HandleStreamingChunkFunction,
    HandleBatchFunction,
    HandleErrorFunction,
    RefreshTokenFunction,
)
from helix_fhir_client_sdk.graph.graph_definition import (
    GraphDefinition,
)
from helix_fhir_client_sdk.graph.simulated_graph_processor_mixin import (
    SimulatedGraphProcessorMixin,
)
from helix_fhir_client_sdk.loggers.fhir_logger import FhirLogger
from helix_fhir_client_sdk.responses.fhir_delete_response import FhirDeleteResponse
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse
from helix_fhir_client_sdk.responses.fhir_update_response import FhirUpdateResponse
from helix_fhir_client_sdk.responses.get_result import GetResult
from helix_fhir_client_sdk.responses.paging_result import PagingResult
from helix_fhir_client_sdk.validators.async_fhir_validator import AsyncFhirValidator
from helix_fhir_client_sdk.well_known_configuration import (
    WellKnownConfigurationCacheEntry,
)


# from urllib3 import Retry  # type: ignore


class FhirClient(SimulatedGraphProcessorMixin):
    """
    Class used to call FHIR server (uses async and parallel execution to speed up)
    """

    _time_to_live_in_secs_for_cache: int = 10 * 60

    # caches result from calls to well known configuration
    #   key is host name of fhir server, value is  auth_server_url
    _well_known_configuration_cache: Dict[str, WellKnownConfigurationCacheEntry] = {}

    # used to lock access to above cache
    _well_known_configuration_cache_lock: Lock = Lock()

    _internal_logger: Logger = logging.getLogger("FhirClient")
    # link handler to logger
    _internal_logger.addHandler(logging.StreamHandler())
    _internal_logger.setLevel(logging.INFO)

    def __init__(self) -> None:
        """
        Class used to call FHIR server (uses async and parallel execution to speed up)
        """
        self._action: Optional[str] = None
        self._action_payload: Optional[Dict[str, Any]] = None
        self._resource: Optional[str] = None
        self._id: Optional[Union[List[str], str]] = None
        self._url: Optional[str] = None
        self._additional_parameters: Optional[List[str]] = None
        self._filter_by_resource: Optional[str] = None
        self._filter_parameter: Optional[str] = None
        self._include_only_properties: Optional[List[str]] = None
        self._page_number: Optional[int] = None
        self._page_size: Optional[int] = None
        self._last_updated_after: Optional[datetime] = None
        self._last_updated_before: Optional[datetime] = None
        self._sort_fields: Optional[List[SortField]] = None
        self._auth_server_url: Optional[str] = None
        self._auth_scopes: Optional[List[str]] = None
        self._login_token: Optional[str] = None
        self._client_id: Optional[str] = None
        self._access_token: Optional[str] = None
        self._logger: Optional[FhirLogger] = None
        self._adapter: Optional[BaseAdapter] = None
        self._limit: Optional[int] = None
        self._validation_server_url: Optional[str] = None
        self._separate_bundle_resources: bool = (
            False  # for each entry in bundle create a property for each resource
        )
        self._obj_id: Optional[str] = None
        self._include_total: bool = False
        self._filters: List[BaseFilter] = []
        self._expand_fhir_bundle: bool = True

        self._stop_processing: bool = False
        self._authentication_token_lock: Lock = Lock()
        self._last_page: Optional[int] = None

        self._use_data_streaming: bool = False
        self._last_page_lock: Lock = Lock()

        self._use_post_for_search: bool = False

        self._accept: str = "application/fhir+json"
        self._content_type: str = "application/fhir+json"
        self._accept_encoding: str = "gzip,deflate"

        self._maximum_time_to_retry_on_429: int = 60 * 60

        self._extra_context_to_return: Optional[Dict[str, Any]] = None

        self._retry_count: int = 2
        self._exclude_status_codes_from_retry: Optional[List[int]] = None

        self._uuid = uuid.uuid4()
        self._log_level: Optional[str] = environ.get("LOGLEVEL")
        # default to built-in function to refresh token
        self._refresh_token_function: RefreshTokenFunction = (
            self.authenticate_async_wrapper()
        )

    def action(self, action: str) -> "FhirClient":
        """
        Set the action

        :param action: (Optional) do an action e.g., $everything
        """
        self._action = action
        return self

    def action_payload(self, action_payload: Dict[str, Any]) -> "FhirClient":
        """
        Set action payload

        :param action_payload: (Optional) if action such as $graph needs a http payload
        """
        self._action_payload = action_payload
        return self

    def resource(self, resource: str) -> "FhirClient":
        """
        set resource to query

        :param resource: what FHIR resource to retrieve
        """
        self._resource = resource
        return self

    def id_(self, id_: Union[List[str], str]) -> "FhirClient":
        self._id = id_
        return self

    def url(self, url: str) -> "FhirClient":
        """
        set url


        :param url: server to call for FHIR
        """
        self._url = url
        return self

    def validation_server_url(self, validation_server_url: str) -> "FhirClient":
        """
        set url to validate


        :param validation_server_url: server to call for FHIR validation
        """
        self._validation_server_url = validation_server_url
        return self

    def additional_parameters(self, additional_parameters: List[str]) -> "FhirClient":
        """
        set additional parameters


        :param additional_parameters: Any additional parameters to send with request
        """
        self._additional_parameters = additional_parameters
        return self

    def filter_by_resource(self, filter_by_resource: str) -> "FhirClient":
        """
        filter


        :param filter_by_resource: filter the resource by this. e.g., /Condition?Patient=1
                (resource=Condition, filter_by_resource=Patient)
        """
        self._filter_by_resource = filter_by_resource
        return self

    def filter_parameter(self, filter_parameter: str) -> "FhirClient":
        """
        filter


        :param filter_parameter: Instead of requesting ?patient=1,
                do ?subject:Patient=1 (if filter_parameter is subject)
        """
        self._filter_parameter = filter_parameter
        return self

    def include_only_properties(
        self, include_only_properties: List[str]
    ) -> "FhirClient":
        """
        include only these properties


        :param include_only_properties: includes only these properties
        """
        self._include_only_properties = include_only_properties
        return self

    def page_number(self, page_number: int) -> "FhirClient":
        """
        page number to load


        :param page_number: page number to load
        """
        self._page_number = page_number
        return self

    def page_size(self, page_size: int) -> "FhirClient":
        """
        page size


        :param page_size: (Optional) use paging and get this many items in each page
        """

        self._page_size = page_size
        return self

    def last_updated_after(self, last_updated_after: datetime) -> "FhirClient":
        """
        get records updated after this datetime


        :param last_updated_after: (Optional) Only get records newer than this
        """
        self._last_updated_after = last_updated_after
        return self

    def last_updated_before(self, last_updated_before: datetime) -> "FhirClient":
        """
        get records updated before this datetime


        :param last_updated_before: (Optional) Only get records older than this
        """
        self._last_updated_before = last_updated_before
        return self

    def sort_fields(self, sort_fields: List[SortField]) -> "FhirClient":
        """
        sort


        :param sort_fields: sort by fields in the resource
        """
        self._sort_fields = sort_fields
        return self

    def auth_server_url(self, auth_server_url: str) -> "FhirClient":
        """
        auth server url


        :param auth_server_url: server url to call to get the authentication token
        """
        self._auth_server_url = auth_server_url
        return self

    def auth_scopes(self, auth_scopes: List[str]) -> "FhirClient":
        """
        auth scopes


        :param auth_scopes: list of scopes to request permission for e.g., system/AllergyIntolerance.read
        """
        assert isinstance(auth_scopes, list), f"{type(auth_scopes)} is not a list"
        self._auth_scopes = auth_scopes
        return self

    def login_token(self, login_token: str) -> "FhirClient":
        """
        login token


        :param login_token: login token to use
        """
        self._login_token = login_token
        return self

    def maximum_time_to_retry_on_429(self, time_in_seconds: int) -> "FhirClient":
        self._maximum_time_to_retry_on_429 = time_in_seconds
        return self

    def extra_context_to_return(self, context: Dict[str, Any]) -> "FhirClient":
        self._extra_context_to_return = context
        return self

    def exclude_status_codes_from_retry(self, status_codes: List[int]) -> "FhirClient":
        self._exclude_status_codes_from_retry = status_codes
        return self

    def retry_count(self, count: int) -> "FhirClient":
        self._retry_count = count
        return self

    def client_credentials(self, client_id: str, client_secret: str) -> "FhirClient":
        """
        Sets client credentials to use when calling the FHIR server


        :param client_id: client_id
        :param client_secret: client_secret
        :return: self
        """
        self._client_id = client_id
        self._login_token = self._create_login_token(
            client_id=client_id, client_secret=client_secret
        )
        logging.info(f"Generated login token for client_id={client_id}")
        return self

    def logger(self, logger: FhirLogger) -> "FhirClient":
        """
        Logger to use for logging calls to the FHIR server


        :param logger: logger
        """
        self._logger = logger
        if self._log_level != "DEBUG":
            # disable internal logger
            self._internal_logger.setLevel(logging.ERROR)
        return self

    def adapter(self, adapter: BaseAdapter) -> "FhirClient":
        """
        Http Adapter to use for calling the FHIR server


        :param adapter: adapter
        """
        self._adapter = adapter
        return self

    def limit(self, limit: int) -> "FhirClient":
        """
        Limit the results


        :param limit: Limit results to this count
        """
        self._limit = limit
        return self

    def use_data_streaming(self, use: bool) -> "FhirClient":
        """
        Use data streaming or not


        :param use: where to use data streaming
        """
        self._use_data_streaming = use
        self._accept = "application/fhir+ndjson"

        return self

    def use_post_for_search(self, use: bool) -> "FhirClient":
        """
        Whether to use POST instead of GET for search


        :param use:
        """
        self._use_post_for_search = use
        return self

    def accept(self, accept_type: str) -> "FhirClient":
        """
        Type to send to server in the request header Accept

        :param accept_type:
        :return:
        """
        self._accept = accept_type
        return self

    def content_type(self, type_: str) -> "FhirClient":
        """
        Type to send to server in the request header Content-Type

        :param type_:
        :return:
        """
        self._content_type = type_
        return self

    def accept_encoding(self, encoding: str) -> "FhirClient":
        """
        Type to send to server in the request header Accept-Encoding

        :param encoding:
        :return:
        """
        self._accept_encoding = encoding
        return self

    def log_level(self, level: Optional[str]) -> "FhirClient":
        self._log_level = level
        return self

    def refresh_token_function(self, fn: RefreshTokenFunction) -> "FhirClient":
        """
        Sets the function to call to refresh the token

        :param fn: function to call to refresh the token
        """
        self._refresh_token_function = fn
        return self

    # noinspection PyUnusedLocal
    @staticmethod
    async def on_request_end(
        session: ClientSession,
        trace_config_ctx: SimpleNamespace,
        params: TraceRequestEndParams,
    ) -> None:
        FhirClient._internal_logger.info(
            "Ending %s request for %s. I sent: %s"
            % (params.method, params.url, params.headers)
        )
        FhirClient._internal_logger.info(
            "Sent headers: %s" % params.response.request_info.headers
        )

    async def get_access_token_async(self) -> Optional[str]:
        """
        Gets current access token


        :return: access token if any
        """
        # if we have an auth server url but no access token then get access token
        if self._login_token and not self._auth_server_url:
            # try to get auth_server_url from well known configuration
            self._auth_server_url = (
                await self._get_auth_server_url_from_well_known_configuration_async()
            )
            if self._auth_server_url:
                logging.info(
                    f"Received {self._auth_server_url} from well_known configuration of server: {self._url}"
                )
        if self._auth_server_url and not self._access_token:
            assert (
                self._login_token
            ), "login token must be present if auth_server_url is set"
            self._access_token = await self._refresh_token_function(
                auth_server_url=self._auth_server_url,
                auth_scopes=self._auth_scopes,
                login_token=self._login_token,
            )
        return self._access_token

    def get_access_token(self) -> Optional[str]:
        return asyncio.run(self.get_access_token_async())

    def set_access_token(self, value: str) -> "FhirClient":
        """
        Sets access token


        :param value: access token
        """
        self._access_token = value
        return self

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

            access_token = await self.get_access_token_async()
            # set access token in request if present
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"

            # actually make the request
            response: ClientResponse = await http.delete(
                full_uri.tostr(), headers=headers
            )
            request_id = response.headers.getone("X-Request-ID", None)
            self._internal_logger.info(f"X-Request-ID={request_id}")
            if response.status == 200:
                if self._logger:
                    self._logger.info(f"Successfully deleted: {full_uri}")

            return FhirDeleteResponse(
                request_id=request_id,
                url=full_uri.tostr(),
                responses=await response.text(),
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

    def separate_bundle_resources(
        self, separate_bundle_resources: bool
    ) -> "FhirClient":
        """
        Set flag to separate bundle resources


        :param separate_bundle_resources:
        """
        self._separate_bundle_resources = separate_bundle_resources
        return self

    def expand_fhir_bundle(self, expand_fhir_bundle: bool) -> "FhirClient":
        """
        Set flag to expand the FHIR bundle into a list of resources. If false then we don't un bundle the response


        :param expand_fhir_bundle: whether to just return the result as a FHIR bundle
        """
        self._expand_fhir_bundle = expand_fhir_bundle
        return self

    async def get_async(
        self, data_chunk_handler: Optional[HandleStreamingChunkFunction] = None
    ) -> FhirGetResponse:
        """
        Issues a GET call

        :return: response
        """
        instance_variables_text = convert_dict_to_str(vars(self))
        if self._logger:
            # self._logger.info(f"LOGLEVEL: {self._log_level}")
            self._logger.info(f"parameters: {instance_variables_text}")
        else:
            self._internal_logger.info(f"LOGLEVEL (InternalLogger): {self._log_level}")
            self._internal_logger.info(f"parameters: {instance_variables_text}")
        ids: Optional[List[str]] = None
        if self._id:
            ids = self._id if isinstance(self._id, list) else [self._id]
        # actually make the request
        async with self.create_http_session() as http:
            return await self._get_with_session_async(
                session=http, ids=ids, fn_handle_streaming_chunk=data_chunk_handler
            )

    def get(self) -> FhirGetResponse:
        """
        Issues a GET call

        :return: response
        """
        result: FhirGetResponse = asyncio.run(self.get_async())
        return result

    async def _get_with_session_async(
        self,
        *,
        session: Optional[ClientSession],
        page_number: Optional[int] = None,
        ids: Optional[List[str]] = None,
        id_above: Optional[str] = None,
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction] = None,
        additional_parameters: Optional[List[str]] = None,
    ) -> FhirGetResponse:
        """
        issues a GET call with the specified session, page_number and ids


        :param session:
        :param page_number:
        :param ids:
        :param id_above: return ids greater than this
        :param fn_handle_streaming_chunk: function to call for each chunk of data
        :param additional_parameters: additional parameters to add to the request
        :return: response
        """
        assert self._url, "No FHIR server url was set"
        assert self._resource, "No Resource was set"
        request_id: Optional[str] = None
        retries_left: int = self._retry_count + 1
        # create url and query to request from FHIR server
        resources_json: str = ""
        full_uri: furl = furl(self._url)
        full_uri /= self._resource
        if self._obj_id:
            full_uri /= parse.quote(str(self._obj_id), safe="")
        if ids is not None and len(ids) > 0:
            if self._filter_by_resource:
                if self._filter_parameter:
                    # ?subject:Patient=27384972
                    full_uri.args[
                        f"{self._filter_parameter}:{self._filter_by_resource}"
                    ] = ",".join(sorted(ids))
                else:
                    # ?patient=27384972
                    full_uri.args[self._filter_by_resource.lower()] = ",".join(
                        sorted(ids)
                    )
            else:
                if len(ids) == 1 and not self._obj_id:
                    full_uri /= ids
                else:
                    full_uri.args["id"] = ",".join(sorted(ids))
        # add action to url
        if self._action:
            full_uri /= self._action
        # add a query for just desired properties
        if self._include_only_properties:
            full_uri.args["_elements"] = ",".join(self._include_only_properties)
        if self._page_size and (
            self._page_number is not None or page_number is not None
        ):
            # noinspection SpellCheckingInspection
            full_uri.args["_count"] = self._page_size
            # noinspection SpellCheckingInspection
            full_uri.args["_getpagesoffset"] = page_number or self._page_number

        if (
            not self._obj_id
            and (ids is None or self._filter_by_resource)
            and self._limit
            and self._limit >= 0
        ):
            full_uri.args["_count"] = self._limit

        # add any sort fields
        if self._sort_fields is not None:
            full_uri.args["_sort"] = ",".join([str(s) for s in self._sort_fields])

        # create full url by adding on any query parameters
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

        if self._include_total:
            if len(full_uri.args) > 0:
                full_url += "&"
            else:
                full_url += "?"
            full_url += "_total=accurate"

        if self._filters and len(self._filters) > 0:
            if len(full_uri.args) > 0:
                full_url += "&"
            else:
                full_url += "?"
            full_url += "&".join(
                set([str(f) for f in self._filters])
            )  # remove any duplicates

        # have to be done here since this arg can be used twice
        if self._last_updated_before:
            if len(full_uri.args) > 0:
                full_url += "&"
            else:
                full_url += "?"
            full_url += f"_lastUpdated=lt{self._last_updated_before.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        if self._last_updated_after:
            if len(full_uri.args) > 0:
                full_url += "&"
            else:
                full_url += "?"
            full_url += f"_lastUpdated=ge{self._last_updated_after.strftime('%Y-%m-%dT%H:%M:%SZ')}"

        if id_above is not None:
            if len(full_uri.args) > 0:
                full_url += "&"
            else:
                full_url += "?"
            full_url += f"id:above={id_above}"

        # set up headers
        payload: Dict[str, str] = self._action_payload if self._action_payload else {}
        headers = {
            "Accept": self._accept,
            "Content-Type": self._content_type,
            "Accept-Encoding": self._accept_encoding,
        }
        start_time: float = time.time()
        last_status_code: Optional[int] = None
        last_response_text: Optional[str] = None
        try:
            while retries_left > 0:
                # set access token in request if present
                access_token: Optional[str] = await self.get_access_token_async()
                if access_token:
                    headers["Authorization"] = f"Bearer {access_token}"

                # actually make the request
                if session is None:
                    http = self.create_http_session()
                else:
                    http = session

                if self._log_level == "DEBUG":
                    if self._logger:
                        self._logger.debug(
                            f"sending a get_with_session_async: {full_url} with client_id={self._client_id} "
                            + f"and scopes={self._auth_scopes} instance_id={self._uuid} retries_left={retries_left}"
                        )
                    if self._internal_logger:
                        self._internal_logger.info(
                            f"sending a get_with_session_async: {full_url} with client_id={self._client_id} "
                            + f"and scopes={self._auth_scopes} instance_id={self._uuid} retries_left={retries_left}"
                        )

                response: ClientResponse = await self._send_fhir_request_async(
                    http, full_url, headers, payload
                )
                last_status_code = response.status
                response_headers: List[str] = [
                    f"{key}:{value}" for key, value in response.headers.items()
                ]
                # retries_left
                retries_left = retries_left - 1
                if self._log_level == "DEBUG":
                    if self._logger:
                        self._logger.info(
                            f"response from get_with_session_async: {full_url} status_code {response.status} "
                            + f"with client_id={self._client_id} and scopes={self._auth_scopes} "
                            + f"instance_id={self._uuid} "
                            + f"retries_left={retries_left}"
                        )
                    if self._internal_logger:
                        self._internal_logger.info(
                            f"response from get_with_session_async: {full_url} status_code {response.status} "
                            + f"with client_id={self._client_id} and scopes={self._auth_scopes} "
                            + f"instance_id={self._uuid} "
                            + f"retries_left={retries_left}"
                        )

                request_id = response.headers.getone("X-Request-ID", None)
                self._internal_logger.info(f"X-Request-ID={request_id}")
                # if using streams, use ndjson content type:
                # async for data, _ in response.content.iter_chunks():
                #     print(data)

                # if request is ok (200) then return the data
                if response.status == 200:
                    total_count: int = 0
                    next_url: Optional[str] = None
                    if self._use_data_streaming:
                        chunk_number = 0
                        line: bytes
                        async for line in response.content:
                            # https://stackoverflow.com/questions/56346811/response-payload-is-not-completed-using-asyncio-aiohttp
                            await asyncio.sleep(0)
                            chunk_number += 1
                            if fn_handle_streaming_chunk:
                                await fn_handle_streaming_chunk(line, chunk_number)
                            if self._logger:
                                self._logger.debug(
                                    f"Successfully retrieved chunk {chunk_number}: {full_url}"
                                )
                            resources_json += line.decode("utf-8")
                    else:
                        if self._logger:
                            self._logger.debug(f"Successfully retrieved: {full_url}")
                        # noinspection PyBroadException
                        try:
                            text = await response.text()
                        except ClientPayloadError as e:
                            # do a retry
                            if self._logger:
                                self._logger.error(
                                    f"{e}: {full_url}: retries_left={retries_left} headers={response.headers}"
                                )
                            continue
                        if len(text) > 0:
                            response_json: Dict[str, Any] = json.loads(text)
                            if (
                                "resourceType" in response_json
                                and response_json["resourceType"] == "Bundle"
                            ):
                                # get next url if present
                                if "link" in response_json:
                                    links: List[Dict[str, Any]] = response_json.get(
                                        "link", []
                                    )
                                    next_links = [
                                        link
                                        for link in links
                                        if link.get("relation") == "next"
                                    ]
                                    if len(next_links) > 0:
                                        next_link: Dict[str, Any] = next_links[0]
                                        next_url = next_link.get("url")

                            # see if this is a Resource Bundle and un-bundle it
                            if (
                                self._expand_fhir_bundle
                                and "resourceType" in response_json
                                and response_json["resourceType"] == "Bundle"
                            ):
                                (
                                    resources_json,
                                    total_count,
                                ) = await self._expand_bundle_async(
                                    resources_json,
                                    response_json,
                                    total_count,
                                    access_token=access_token,
                                    url=self._url,
                                )
                            elif (
                                self._separate_bundle_resources
                                and "resourceType" in response_json
                                and response_json["resourceType"] != "Bundle"
                            ):
                                # single resource was returned
                                resources_dict = {
                                    f'{response_json["resourceType"].lower()}': [
                                        response_json
                                    ],
                                    "token": access_token,
                                    "url": self._url,
                                }
                                if self._extra_context_to_return:
                                    resources_dict.update(self._extra_context_to_return)

                                resources_json = json.dumps(resources_dict)
                            else:
                                resources_json = text
                    return FhirGetResponse(
                        request_id=request_id,
                        url=full_url,
                        responses=resources_json,
                        error=None,
                        access_token=self._access_token,
                        total_count=total_count,
                        status=response.status,
                        next_url=next_url,
                        extra_context_to_return=self._extra_context_to_return,
                        resource_type=self._resource,
                        id_=self._id,
                        response_headers=response_headers,
                    )
                elif response.status == 404:  # not found
                    last_response_text = await self.get_safe_response_text_async(
                        response=response
                    )
                    if self._logger:
                        self._logger.error(f"resource not found! {full_url}")
                    return FhirGetResponse(
                        request_id=request_id,
                        url=full_url,
                        responses=await response.text(),
                        error="NotFound",
                        access_token=self._access_token,
                        total_count=0,
                        status=response.status,
                        extra_context_to_return=self._extra_context_to_return,
                        resource_type=self._resource,
                        id_=self._id,
                        response_headers=response_headers,
                    )
                elif response.status == 502 or response.status == 504:  # time out
                    last_response_text = await self.get_safe_response_text_async(
                        response=response
                    )
                    if retries_left > 0 and (
                        not self._exclude_status_codes_from_retry
                        or response.status not in self._exclude_status_codes_from_retry
                    ):
                        continue
                elif response.status == 403:  # forbidden
                    last_response_text = await self.get_safe_response_text_async(
                        response=response
                    )
                    return FhirGetResponse(
                        request_id=request_id,
                        url=full_url,
                        responses=await response.text(),
                        error=None,
                        access_token=self._access_token,
                        total_count=0,
                        status=response.status,
                        extra_context_to_return=self._extra_context_to_return,
                        resource_type=self._resource,
                        id_=self._id,
                        response_headers=response_headers,
                    )
                elif response.status == 401:  # unauthorized
                    last_response_text = await self.get_safe_response_text_async(
                        response=response
                    )
                    if retries_left > 0 and (
                        not self._exclude_status_codes_from_retry
                        or response.status not in self._exclude_status_codes_from_retry
                    ):
                        if not self._auth_server_url or not self._login_token:
                            # no ability to refresh auth token
                            return FhirGetResponse(
                                request_id=request_id,
                                url=full_url,
                                responses="",
                                error=last_response_text or "UnAuthorized",
                                access_token=self._access_token,
                                total_count=0,
                                status=response.status,
                                extra_context_to_return=self._extra_context_to_return,
                                resource_type=self._resource,
                                id_=self._id,
                                response_headers=response_headers,
                            )
                        assert (
                            self._auth_server_url
                        ), f"{response.status} received from server but no auth_server_url was specified to use"
                        assert (
                            self._login_token
                        ), f"{response.status} received from server but no login_token was specified to use"
                        self._access_token = await self._refresh_token_function(
                            auth_server_url=self._auth_server_url,
                            auth_scopes=self._auth_scopes,
                            login_token=self._login_token,
                        )
                        # try again
                        continue
                    else:
                        # out of retries_left so just fail now
                        return FhirGetResponse(
                            request_id=request_id,
                            url=full_url,
                            responses=await response.text(),
                            error=None,
                            access_token=self._access_token,
                            total_count=0,
                            status=response.status,
                            extra_context_to_return=self._extra_context_to_return,
                            resource_type=self._resource,
                            id_=self._id,
                            response_headers=response_headers,
                        )
                elif response.status == 429:  # too many calls
                    last_response_text = await self.get_safe_response_text_async(
                        response=response
                    )
                    if (
                        not self._exclude_status_codes_from_retry
                        or response.status not in self._exclude_status_codes_from_retry
                    ):
                        return FhirGetResponse(
                            request_id=request_id,
                            url=full_url,
                            responses=await response.text(),
                            error=None,
                            access_token=self._access_token,
                            total_count=0,
                            status=response.status,
                            extra_context_to_return=self._extra_context_to_return,
                            resource_type=self._resource,
                            id_=self._id,
                            response_headers=response_headers,
                        )
                    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/429
                    # read the Retry-After header
                    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Retry-After
                    retry_after_text: str = str(response.headers.getone("Retry-After"))
                    if self._logger:
                        self._logger.info(
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
                    if self._logger:
                        self._logger.info(
                            f"Finished waiting after a 429 with retry-after: {retry_after_text}"
                        )
                    continue
                else:
                    # some unexpected error
                    if self._logger:
                        self._logger.error(
                            f"Fhir Receive failed [{response.status}]: {full_url} "
                        )
                    if self._internal_logger:
                        self._internal_logger.error(
                            f"Fhir Receive failed [{response.status}]: {full_url} "
                        )
                    error_text: str = await self.get_safe_response_text_async(
                        response=response
                    )
                    if self._logger:
                        self._logger.error(error_text)
                    if self._internal_logger:
                        self._internal_logger.error(error_text)

                    return FhirGetResponse(
                        request_id=request_id,
                        url=full_url,
                        responses=error_text,
                        access_token=self._access_token,
                        error=error_text,
                        total_count=0,
                        status=response.status,
                        extra_context_to_return=self._extra_context_to_return,
                        resource_type=self._resource,
                        id_=self._id,
                        response_headers=response_headers,
                    )

                if self._logger:
                    self._logger.info(
                        f"Got status_code= {response.status}, Retries left={retries_left}"
                    )
                if self._internal_logger:
                    self._internal_logger.info(
                        f"Got status_code= {response.status}, Retries left={retries_left}"
                    )

            # if after retries_left we still fail then show it here
            return FhirGetResponse(
                request_id=request_id,
                url=full_url,
                responses="",
                error=last_response_text or "Error after retries",
                access_token=self._access_token,
                total_count=0,
                status=last_status_code or 0,
                extra_context_to_return=self._extra_context_to_return,
                resource_type=self._resource,
                id_=self._id,
                response_headers=None,
            )
        except Exception as ex:
            raise FhirSenderException(
                request_id=request_id,
                exception=ex,
                url=full_url,
                headers=headers,
                json_data="",
                variables=vars(self),
                response_text=last_response_text,
                response_status_code=last_status_code,
                message="",
                elapsed_time=time.time() - start_time,
            )

    async def _expand_bundle_async(
        self,
        resources: str,
        response_json: Dict[str, Any],
        total_count: int,
        access_token: Optional[str],
        url: str,
    ) -> Tuple[str, int]:
        if "total" in response_json:
            total_count = int(response_json["total"])
        if "entry" in response_json:
            entries: List[Dict[str, Any]] = response_json["entry"]
            entry: Dict[str, Any]
            resources_list: List[Dict[str, Any]] = []
            for entry in entries:
                if "resource" in entry:
                    if self._separate_bundle_resources:
                        await self._separate_contained_resources_async(
                            entry=entry,
                            resources_list=resources_list,
                            access_token=access_token,
                            url=url,
                        )
                    else:
                        resources_list.append(entry["resource"])

            resources = json.dumps(resources_list)
        return resources, total_count

    async def _separate_contained_resources_async(
        self,
        *,
        entry: Dict[str, Any],
        resources_list: List[Dict[str, Any]],
        access_token: Optional[str],
        url: str,
    ) -> None:
        # if self._action != "$graph":
        #     raise Exception(
        #         "only $graph action with _separate_bundle_resources=True"
        #         " is supported at this moment"
        #     )
        resources_dict: Dict[
            str, Union[Optional[str], List[Any]]
        ] = {}  # {resource type: [data]}}
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
        if self._extra_context_to_return:
            resources_dict.update(self._extra_context_to_return)
        resources_list.append(resources_dict)

    async def _send_fhir_request_async(
        self,
        http: ClientSession,
        full_url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
    ) -> ClientResponse:
        """
        Sends a request to the server


        :param http: session to use
        :param full_url: url to call
        :param headers: headers to send
        :param payload: payload to send
        """
        if self._action == "$graph":
            if self._logger:
                self._logger.info(
                    f"sending a post: {full_url} with client_id={self._client_id} and scopes={self._auth_scopes}"
                )
            logging.info(
                f"sending a post: {full_url} with client_id={self._client_id} and scopes={self._auth_scopes}"
            )
            if payload:
                return await http.post(full_url, headers=headers, json=payload)
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
            return await http.get(full_url, headers=headers, data=payload)

    # noinspection SpellCheckingInspection
    def create_http_session(self) -> ClientSession:
        """
        Creates an HTTP Session

        """
        # retry_strategy = Retry(
        #     total=5,
        #     status_forcelist=[429, 500, 502, 503, 504],
        #     method_whitelist=[
        #         "HEAD",
        #         "GET",
        #         "PUT",
        #         "DELETE",
        #         "OPTIONS",
        #         "TRACE",
        #         "POST",
        #     ],
        #     backoff_factor=5,
        # )
        # session: ClientSession = aiohttp.ClientSession()
        trace_config = aiohttp.TraceConfig()
        # trace_config.on_request_start.append(on_request_start)
        if self._log_level == "DEBUG":
            trace_config.on_request_end.append(FhirClient.on_request_end)
        # trace_config.on_response_chunk_received
        # https://stackoverflow.com/questions/56346811/response-payload-is-not-completed-using-asyncio-aiohttp
        timeout = aiohttp.ClientTimeout(total=60 * 60, sock_read=240)
        session: ClientSession = aiohttp.ClientSession(
            trace_configs=[trace_config],
            headers={"Connection": "keep-alive"},
            timeout=timeout,
        )
        return session

    async def get_with_handler_async(
        self,
        session: Optional[ClientSession],
        page_number: Optional[int],
        ids: Optional[List[str]],
        fn_handle_batch: Optional[HandleBatchFunction],
        fn_handle_error: Optional[HandleErrorFunction],
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction] = None,
        id_above: Optional[str] = None,
    ) -> GetResult:
        """
        gets data and calls the handlers as data is received


        :param fn_handle_streaming_chunk:
        :param session:
        :param page_number:
        :param ids: ids to retrieve
        :param fn_handle_batch: function to call when data is received
        :param fn_handle_error: function to call when there is an error
        :param id_above:
        :return: list of resources
        """
        result: FhirGetResponse = await self._get_with_session_async(
            session=session,
            page_number=page_number,
            ids=ids,
            id_above=id_above,
            fn_handle_streaming_chunk=fn_handle_streaming_chunk,
        )
        if result.error:
            if fn_handle_error:
                await fn_handle_error(result.error, result.responses, page_number)
        elif not result.error and bool(result.responses):
            result_list: List[Dict[str, Any]] = []
            if self._use_data_streaming:
                # convert ndjson to a list
                assert isinstance(result.responses, str)
                ndjson_content = result.responses
                for ndjson_line in ndjson_content.splitlines():
                    if not ndjson_line.strip():
                        continue  # ignore empty lines
                    json_line = json.loads(ndjson_line)
                    result_list.append(json_line)
            else:
                result_list = json.loads(result.responses)
                if isinstance(result_list, dict):
                    result_list = [result_list]
                assert isinstance(result_list, list)
            if fn_handle_batch:
                handle_batch_result: bool = await fn_handle_batch(
                    result_list, page_number
                )
                if handle_batch_result is False:
                    self._stop_processing = True
            return GetResult(
                request_id=result.request_id,
                resources=result_list,
                response_headers=result.response_headers,
            )
        return GetResult(
            request_id=result.request_id,
            resources=[],
            response_headers=result.response_headers,
        )

    async def get_page_by_query_async(
        self,
        session: Optional[ClientSession],
        start_page: int,
        increment: int,
        output_queue: asyncio.Queue[PagingResult],
        fn_handle_batch: Optional[HandleBatchFunction],
        fn_handle_error: Optional[HandleErrorFunction],
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction],
    ) -> List[PagingResult]:
        """
        Gets the specified page for query

        :param fn_handle_streaming_chunk:
        :param session:
        :param start_page:
        :param increment:
        :param output_queue: queue to use
        :param fn_handle_batch: function to call when data is received
        :param fn_handle_error: function to call when there is an error
        :return: list of paging results
        """
        page_number: int = start_page
        server_page_number: int = page_number
        result: List[PagingResult] = []
        id_above: Optional[str] = None
        while (
            not self._last_page and not self._last_page == 0
        ) or page_number < self._last_page:
            result_for_page: GetResult = await self.get_with_handler_async(
                session=session,
                page_number=server_page_number,
                ids=None,
                fn_handle_batch=fn_handle_batch,
                fn_handle_error=fn_handle_error,
                fn_handle_streaming_chunk=fn_handle_streaming_chunk,
                id_above=id_above,
            )
            if result_for_page and len(result_for_page.resources) > 0:
                paging_result = PagingResult(
                    request_id=result_for_page.request_id,
                    resources=result_for_page.resources,
                    page_number=page_number,
                    response_headers=result_for_page.response_headers,
                )
                await output_queue.put(paging_result)
                result.append(paging_result)
            else:
                with self._last_page_lock:
                    if not self._last_page or page_number < self._last_page:
                        self._last_page = page_number
                        if self._logger:
                            self._logger.info(f"Setting last page to {self._last_page}")
                break
            # get id of last resource to use as minimum for next page
            last_json_resource = result_for_page.resources[-1]
            if "id" in last_json_resource:
                # use id:above to optimize the next query
                id_above = last_json_resource["id"]
            server_page_number = increment - 1
            page_number = page_number + increment
        return result

    async def _get_page_by_query_tasks_async(
        self,
        concurrent_requests: int,
        output_queue: asyncio.Queue[PagingResult],
        fn_handle_batch: Optional[HandleBatchFunction],
        fn_handle_error: Optional[HandleErrorFunction],
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction],
        http: ClientSession,
    ) -> AsyncGenerator[Coroutine[Any, Any, List[PagingResult]], None]:
        """
        Returns tasks to get pages by query


        :param concurrent_requests:
        :param output_queue:
        :param fn_handle_batch: function to call when data is received
        :param fn_handle_error: function to call when there is an error
        :param http: session
        :return: task
        """
        for taskNumber in range(concurrent_requests):
            yield (
                self.get_page_by_query_async(
                    session=http,
                    start_page=taskNumber,
                    increment=concurrent_requests,
                    output_queue=output_queue,
                    fn_handle_batch=fn_handle_batch,
                    fn_handle_error=fn_handle_error,
                    fn_handle_streaming_chunk=fn_handle_streaming_chunk,
                )
            )

    async def get_by_query_in_pages_async(
        self,
        concurrent_requests: int,
        output_queue: asyncio.Queue[PagingResult],
        fn_handle_batch: Optional[HandleBatchFunction],
        fn_handle_error: Optional[HandleErrorFunction],
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction],
    ) -> FhirGetResponse:
        """
        Retrieves the data in batches (using paging) to reduce load on the FHIR server and to reduce network traffic


        :param fn_handle_streaming_chunk:
        :param output_queue:
        :type output_queue:
        :param fn_handle_error:
        :param concurrent_requests:
        :param fn_handle_batch: function to call for each batch.  Receives a list of resources where each
                                    resource is a dictionary. If this is specified then we don't return
                                    the resources anymore.  If this function returns False then we stop
                                    processing batches.
        :return response containing all the resources received
        """
        # if paging is requested then iterate through the pages until the response is empty
        assert self._url
        assert self._page_size
        self._page_number = 0
        self._stop_processing = False
        resources_list: List[Dict[str, Any]] = []

        async with self.create_http_session() as http:
            first_completed: Future[List[PagingResult]]
            for first_completed in asyncio.as_completed(
                [
                    task
                    async for task in self._get_page_by_query_tasks_async(
                        http=http,
                        output_queue=output_queue,
                        concurrent_requests=concurrent_requests,
                        fn_handle_batch=fn_handle_batch,
                        fn_handle_error=fn_handle_error,
                        fn_handle_streaming_chunk=fn_handle_streaming_chunk,
                    )
                ]
            ):
                result_list: List[PagingResult] = await first_completed
                for resources in [r.resources for r in result_list]:
                    resources_list.extend(resources)

            return FhirGetResponse(
                request_id=result_list[0].request_id if len(result_list) > 0 else None,
                url=self._url,
                responses=json.dumps(resources_list),
                error=None,
                access_token=self._access_token,
                total_count=len(resources_list),
                status=200,
                extra_context_to_return=self._extra_context_to_return,
                resource_type=self._resource,
                id_=self._id,
                response_headers=result_list[0].response_headers
                if len(result_list) > 0
                else None,
            )

    @staticmethod
    def _create_login_token(client_id: str, client_secret: str) -> str:
        """
        Creates a login token given client_id and client_secret


        :return: login token
        """
        token: str = base64.b64encode(
            f"{client_id}:{client_secret}".encode("ascii")
        ).decode("ascii")
        return token

    @staticmethod
    async def authenticate_async(
        *,
        session: ClientSession,
        auth_server_url: str,
        auth_scopes: Optional[List[str]],
        login_token: Optional[str],
    ) -> Optional[str]:
        assert auth_server_url
        assert auth_scopes
        assert login_token
        payload: str = (
            "grant_type=client_credentials&scope=" + "%20".join(auth_scopes)
            if auth_scopes
            else ""
        )
        # noinspection SpellCheckingInspection
        headers: Dict[str, str] = {
            "Accept": "application/json",
            "Authorization": "Basic " + login_token,
            "Content-Type": "application/x-www-form-urlencoded",
        }

        response: ClientResponse = await session.request(
            "POST", auth_server_url, headers=headers, data=payload
        )

        # token = response.text.encode('utf8')
        token_text: str = await response.text()
        if not token_text:
            return None
        token_json: Dict[str, Any] = json.loads(token_text)

        if "access_token" not in token_json:
            raise Exception(f"No access token found in {token_json}")
        access_token: str = token_json["access_token"]
        return access_token

    def authenticate_async_wrapper(self) -> RefreshTokenFunction:
        """
        Returns a function that authenticates with auth server


        :return: refresh token function
        """

        async def refresh_token(
            auth_server_url: str,
            auth_scopes: Optional[List[str]],
            login_token: Optional[str],
        ) -> Optional[str]:
            """
            This function creates the session and then calls authenticate_async()

            :param auth_server_url: auth server url
            :param auth_scopes: auth scopes
            :param login_token: login token
            :return: access token
            """
            async with self.create_http_session() as session:
                with self._authentication_token_lock:
                    return await self.authenticate_async(
                        session=session,
                        auth_server_url=auth_server_url,
                        auth_scopes=auth_scopes,
                        login_token=login_token,
                    )

        return refresh_token

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
        async with self.create_http_session() as http:
            # Set up headers
            headers = {"Content-Type": "application/json-patch+json"}
            access_token = await self.get_access_token_async()
            # set access token in request if present
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
            response: Optional[ClientResponse] = None
            try:
                deserialized_data = json.loads(data)
                # Make the request
                response = await http.patch(
                    url=full_uri.url, json=deserialized_data, headers=headers
                )
                response_status = response.status
                request_id = response.headers.getone("X-Request-ID", None)
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
                    response_text=await self.get_safe_response_text_async(
                        response=response
                    ),
                    response_status_code=response.status if response else None,
                    exception=e,
                    variables=vars(self),
                    message=f"Error: {e}",
                    elapsed_time=time.time() - start_time,
                ) from e
            # check if response is json
            response_text = await response.text()
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
            )

    def send_patch_request(self, data: str) -> FhirUpdateResponse:
        """
        Update the resource.  This will partially update an existing resource with changes specified in the request.
        :param data: data to update the resource with
        """
        result: FhirUpdateResponse = asyncio.run(self.send_patch_request_async(data))
        return result

    async def merge_async(
        self,
        *,
        id_: Optional[str] = None,
        json_data_list: List[str],
    ) -> FhirMergeResponse:
        """
        Calls $merge function on FHIR server


        :param json_data_list: list of resources to send
        :param id_: id of the resource to merge
        :return: response
        """
        assert self._url, "No FHIR server url was set"
        assert isinstance(json_data_list, list), "This function requires a list"

        self._internal_logger.debug(
            f"Calling $merge on {self._url} with client_id={self._client_id} and scopes={self._auth_scopes}"
        )
        instance_variables_text = convert_dict_to_str(vars(self))
        if self._internal_logger:
            self._internal_logger.info(f"parameters: {instance_variables_text}")
        else:
            self._internal_logger.info(f"LOGLEVEL (InternalLogger): {self._log_level}")
            self._internal_logger.info(f"parameters: {instance_variables_text}")

        request_id: Optional[str] = None
        response_status: Optional[int] = None
        retries: int = 2
        while retries >= 0:
            retries = retries - 1
            full_uri: furl = furl(self._url)
            assert self._resource
            full_uri /= self._resource
            headers = {"Content-Type": "application/fhir+json"}
            responses: List[Dict[str, Any]] = []
            start_time: float = time.time()
            async with self.create_http_session() as http:
                # set access token in request if present
                if await self.get_access_token_async():
                    headers[
                        "Authorization"
                    ] = f"Bearer {await self.get_access_token_async()}"

                try:
                    resource_json_list_incoming: List[Dict[str, Any]] = [
                        json.loads(json_data) for json_data in json_data_list
                    ]
                    resource_json_list_clean: List[Dict[str, Any]] = []
                    errors: List[Dict[str, Any]] = []
                    if self._validation_server_url:
                        resource_json: Dict[str, Any]
                        # if there is only resource then just validate that individually
                        if len(resource_json_list_incoming) == 1:
                            try:
                                resource_json = resource_json_list_incoming[0]
                                await AsyncFhirValidator.validate_fhir_resource(
                                    http=http,
                                    json_data=json.dumps(resource_json),
                                    resource_name=resource_json.get("resourceType")
                                    or self._resource,
                                    validation_server_url=self._validation_server_url,
                                )
                                resource_json_list_clean.append(resource_json)
                            except FhirValidationException as e:
                                errors.append(
                                    {
                                        "id": resource_json.get("id"),
                                        "resourceType": resource_json.get(
                                            "resourceType"
                                        ),
                                        "issue": e.issue,
                                    }
                                )
                        else:
                            for resource_json in resource_json_list_incoming:
                                try:
                                    await AsyncFhirValidator.validate_fhir_resource(
                                        http=http,
                                        json_data=json.dumps(resource_json),
                                        resource_name=resource_json.get("resourceType")
                                        or self._resource,
                                        validation_server_url=self._validation_server_url,
                                    )
                                    resource_json_list_clean.append(resource_json)
                                except FhirValidationException as e:
                                    errors.append(
                                        {
                                            "id": resource_json.get("id"),
                                            "resourceType": resource_json.get(
                                                "resourceType"
                                            ),
                                            "issue": e.issue,
                                        }
                                    )
                    else:
                        resource_json_list_clean = resource_json_list_incoming

                    resource_uri: furl = full_uri.copy()
                    if len(resource_json_list_clean) > 0:
                        # if there is only item in the list then send it instead of having it in a list
                        json_payload: str = (
                            json.dumps(resource_json_list_clean[0])
                            if len(resource_json_list_clean) == 1
                            else json.dumps(resource_json_list_clean)
                        )
                        # json_payload_bytes: str = json_payload
                        json_payload_bytes: bytes = json_payload.encode("utf-8")
                        obj_id = (
                            id_ or 1
                        )  # TODO: remove this once the node fhir accepts merge without a parameter
                        assert obj_id

                        resource_uri /= parse.quote(str(obj_id), safe="")
                        resource_uri /= "$merge"
                        response: Optional[ClientResponse] = None
                        try:
                            # should we check if it exists and do a POST then?
                            response = await http.post(
                                url=resource_uri.url,
                                data=json_payload_bytes,
                                headers=headers,
                            )
                            response_status = response.status
                            request_id = response.headers.getone("X-Request-ID", None)
                            self._internal_logger.info(f"X-Request-ID={request_id}")
                            if response and response.status == 200:
                                # logging does not work in UDFs since they run on nodes
                                # if progress_logger:
                                #     progress_logger.write_to_log(
                                #         f"Posted to {resource_uri.url}: {json_data}"
                                #     )
                                # check if response is json
                                response_text = await response.text()
                                if response_text:
                                    try:
                                        raw_response: Union[
                                            List[Dict[str, Any]], Dict[str, Any]
                                        ] = json.loads(response_text)
                                        if isinstance(raw_response, list):
                                            responses = raw_response
                                        else:
                                            responses = [raw_response]
                                    except ValueError as e:
                                        responses = [{"issue": str(e)}]
                                else:
                                    responses = []
                            elif (
                                response.status == 403 or response.status == 401
                            ):  # forbidden or unauthorized
                                if retries >= 0:
                                    assert self._auth_server_url, (
                                        f"{response.status} received from server but no auth_server_url"
                                        " was specified to use"
                                    )
                                    assert (
                                        self._login_token
                                    ), f"{response.status} received from server but no login_token was specified to use"
                                    self._access_token = (
                                        await self._refresh_token_function(
                                            auth_server_url=self._auth_server_url,
                                            auth_scopes=self._auth_scopes,
                                            login_token=self._login_token,
                                        )
                                    )
                                    # try again
                                    continue
                                else:
                                    # out of retries so just fail now
                                    response.raise_for_status()
                            else:  # other HTTP errors
                                self._internal_logger.info(
                                    f"POST response for {resource_uri.url}: {response.status}"
                                )
                                response_text = await self.get_safe_response_text_async(
                                    response=response
                                )
                                return FhirMergeResponse(
                                    request_id=request_id,
                                    url=resource_uri.url or self._url or "",
                                    json_data=json_payload,
                                    responses=[
                                        {
                                            "issue": [
                                                {
                                                    "severity": "error",
                                                    "code": "exception",
                                                    "diagnostics": response_text,
                                                }
                                            ]
                                        }
                                    ],
                                    error=json.dumps(response_text)
                                    if response_text
                                    else None,
                                    access_token=self._access_token,
                                    status=response.status if response.status else 500,
                                )
                        except requests.exceptions.HTTPError as e:
                            raise FhirSenderException(
                                request_id=request_id,
                                url=resource_uri.url,
                                headers=headers,
                                json_data=json_payload,
                                response_text=await self.get_safe_response_text_async(
                                    response=response
                                ),
                                response_status_code=response.status
                                if response
                                else None,
                                exception=e,
                                variables=vars(self),
                                message=f"HttpError: {e}",
                                elapsed_time=time.time() - start_time,
                            ) from e
                        except Exception as e:
                            raise FhirSenderException(
                                request_id=request_id,
                                url=resource_uri.url,
                                headers=headers,
                                json_data=json_payload,
                                response_text=await self.get_safe_response_text_async(
                                    response=response
                                ),
                                response_status_code=response.status
                                if response
                                else None,
                                exception=e,
                                variables=vars(self),
                                message=f"Unknown Error: {e}",
                                elapsed_time=time.time() - start_time,
                            ) from e
                    else:
                        json_payload = json.dumps(json_data_list)

                except AssertionError as e:
                    if self._logger:
                        self._logger.error(
                            Exception(
                                f"Assertion: FHIR send failed: {str(e)} for resource: {json_data_list}. "
                                + f"variables={convert_dict_to_str(vars(self))}"
                            )
                        )

                return FhirMergeResponse(
                    request_id=request_id,
                    url=resource_uri.url,
                    responses=responses + errors,
                    error=json.dumps(responses + errors)
                    if response_status != 200
                    else None,
                    access_token=self._access_token,
                    status=response_status if response_status else 500,
                    json_data=json_payload,
                )

        raise Exception(
            f"Could not talk to FHIR server after multiple tries: {request_id}"
        )

    # noinspection PyMethodMayBeStatic
    async def get_safe_response_text_async(
        self, response: Optional[ClientResponse]
    ) -> str:
        try:
            return (
                await response.text() if (response and response.status != 504) else ""
            )
        except Exception as e:
            return str(e)

    def merge(
        self,
        *,
        id_: Optional[str] = None,
        json_data_list: List[str],
    ) -> FhirMergeResponse:
        """
        Calls $merge function on FHIR server


        :param json_data_list: list of resources to send
        :param id_: id of the resource to merge
        :return: response
        """
        result: FhirMergeResponse = asyncio.run(
            self.merge_async(id_=id_, json_data_list=json_data_list)
        )
        return result

    async def _get_auth_server_url_from_well_known_configuration_async(
        self,
    ) -> Optional[str]:
        """
        Finds the auth server url via the well known configuration if it exists


        :return: auth server url or None
        """
        full_uri: furl = furl(furl(self._url).origin)
        host_name: str = full_uri.tostr()
        if host_name in self._well_known_configuration_cache:
            entry: Optional[
                WellKnownConfigurationCacheEntry
            ] = self._well_known_configuration_cache.get(host_name)
            if entry and (
                (datetime.utcnow() - entry.last_updated_utc).seconds
                < self._time_to_live_in_secs_for_cache
            ):
                cached_endpoint: Optional[str] = entry.auth_url
                # self._internal_logger.info(
                #     f"Returning auth_url from cache for {host_name}: {cached_endpoint}"
                # )
                return cached_endpoint
        full_uri /= ".well-known/smart-configuration"
        self._internal_logger.info(f"Calling {full_uri.tostr()}")
        async with self.create_http_session() as http:
            try:
                response: ClientResponse = await http.get(full_uri.tostr())
                text_ = await response.text()
                if response and response.status == 200 and text_:
                    content: Dict[str, Any] = json.loads(text_)
                    token_endpoint: Optional[str] = str(content["token_endpoint"])
                    with self._well_known_configuration_cache_lock:
                        self._well_known_configuration_cache[
                            host_name
                        ] = WellKnownConfigurationCacheEntry(
                            auth_url=token_endpoint, last_updated_utc=datetime.utcnow()
                        )
                    return token_endpoint
                else:
                    with self._well_known_configuration_cache_lock:
                        self._well_known_configuration_cache[
                            host_name
                        ] = WellKnownConfigurationCacheEntry(
                            auth_url=None, last_updated_utc=datetime.utcnow()
                        )
                    return None
            except Exception as e:
                raise Exception(
                    f"Error getting well known configuration from {full_uri.tostr()}"
                ) from e

    async def graph_async(
        self,
        *,
        id_: Optional[str] = None,
        graph_definition: GraphDefinition,
        contained: bool,
        process_in_batches: Optional[bool] = None,
        fn_handle_batch: Optional[HandleBatchFunction] = None,
        fn_handle_error: Optional[HandleErrorFunction] = None,
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction] = None,
        concurrent_requests: int = 1,
    ) -> FhirGetResponse:
        """
        Executes the $graph query on the FHIR server


        :param fn_handle_streaming_chunk:
        :type fn_handle_streaming_chunk:
        :param concurrent_requests:
        :param graph_definition: definition of a graph to execute
        :param contained: whether we should return the related resources as top level list or nest them inside their
                            parent resources in a contained property
        :param process_in_batches: whether to process in batches of size page_size
        :param fn_handle_batch: Optional function to execute on each page of data.  Note that if this is passed we don't
                                return the resources in the response anymore.  If this function returns false then we
                                stop processing any further batches.
        :param fn_handle_error: function that is called when there is an error
        :param id_: id of the resource to start the graph from
        :return: response containing all the resources received
        """
        assert graph_definition
        assert isinstance(graph_definition, GraphDefinition)
        assert graph_definition.start
        if contained:
            if not self._additional_parameters:
                self._additional_parameters = []
            self._additional_parameters.append("contained=true")
        self.action_payload(graph_definition.to_dict())
        self.resource(graph_definition.start)
        self.action("$graph")
        self._obj_id = (
            id_ or "1"
        )  # this is needed because the $graph endpoint requires an id
        output_queue: asyncio.Queue[PagingResult] = asyncio.Queue()
        async with self.create_http_session() as http:
            return (
                await self._get_with_session_async(
                    session=http, fn_handle_streaming_chunk=fn_handle_streaming_chunk
                )
                if not process_in_batches
                else await self.get_by_query_in_pages_async(
                    concurrent_requests=concurrent_requests,
                    output_queue=output_queue,
                    fn_handle_error=fn_handle_error,
                    fn_handle_batch=fn_handle_batch,
                    fn_handle_streaming_chunk=fn_handle_streaming_chunk,
                )
            )

    def graph(
        self,
        *,
        graph_definition: GraphDefinition,
        contained: bool,
        process_in_batches: Optional[bool] = None,
        concurrent_requests: int = 1,
    ) -> FhirGetResponse:
        return asyncio.run(
            self.graph_async(
                graph_definition=graph_definition,
                contained=contained,
                process_in_batches=process_in_batches,
                concurrent_requests=concurrent_requests,
            )
        )

    def include_total(self, include_total: bool) -> "FhirClient":
        """
        Whether to ask the server to include the total count in the result


        :param include_total: whether to include total count
        """
        self._include_total = include_total
        return self

    def filter(self, filter_: List[BaseFilter]) -> "FhirClient":
        """
        Allows adding in a custom filters that derives from BaseFilter


        :param filter_: list of custom filter instances that derives from BaseFilter.
        """
        assert isinstance(filter_, list), "This function requires a list"
        self._filters.extend(filter_)
        return self

    async def update_async(self, json_data: str) -> FhirUpdateResponse:
        """
        Update the resource.  This will completely overwrite the resource.  We recommend using merge()
            instead since that does proper merging.


        :param json_data: data to update the resource with
        """
        assert self._url, "No FHIR server url was set"
        assert json_data, "Empty string was passed"
        if not self._id:
            raise ValueError("update requires the ID of FHIR object to update")
        if not isinstance(self._id, str):
            raise ValueError("update should have only one id")
        if not self._resource:
            raise ValueError("update requires a FHIR resource type")
        full_uri: furl = furl(self._url)
        full_uri /= self._resource
        full_uri /= self._id
        # setup retry
        async with self.create_http_session() as http:
            # set up headers
            headers = {"Content-Type": "application/fhir+json"}

            access_token = await self.get_access_token_async()
            # set access token in request if present
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"

            if self._validation_server_url:
                await AsyncFhirValidator.validate_fhir_resource(
                    http=http,
                    json_data=json_data,
                    resource_name=self._resource,
                    validation_server_url=self._validation_server_url,
                )

            json_payload_bytes: bytes = json_data.encode("utf-8")
            # actually make the request
            response = await http.put(
                url=full_uri.url, data=json_payload_bytes, headers=headers
            )
            request_id = response.headers.getone("X-Request-ID", None)
            self._internal_logger.info(f"X-Request-ID={request_id}")
            if response.status == 200:
                if self._logger:
                    self._logger.info(f"Successfully updated: {full_uri}")

            return FhirUpdateResponse(
                request_id=request_id,
                url=full_uri.tostr(),
                responses=await response.text(),
                error=f"{response.status}" if not response.status == 200 else None,
                access_token=access_token,
                status=response.status,
            )

    def update(self, json_data: str) -> FhirUpdateResponse:
        """
        Update the resource.  This will completely overwrite the resource.  We recommend using merge()
            instead since that does proper merging.


        :param json_data: data to update the resource with
        """
        result: FhirUpdateResponse = asyncio.run(self.update_async(json_data))
        return result

    async def get_resources_by_id_in_parallel_batches_async(
        self,
        concurrent_requests: int,
        chunks: Generator[List[str], None, None],
        fn_handle_batch: Optional[HandleBatchFunction],
        fn_handle_error: Optional[HandleErrorFunction],
        fn_handle_ids: Optional[HandleBatchFunction] = None,
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction] = None,
    ) -> List[Dict[str, Any]]:
        """
        Given a list of ids, this function loads them in parallel batches


        :param concurrent_requests:
        :param chunks: a generator that returns a list of ids to load in one batch
        :param fn_handle_batch: Optional function to execute on each page of data.  Note that if this is passed we don't
                                return the resources in the response anymore.  If this function returns false then we
                                stop processing any further batches.
        :param fn_handle_error: function that is called when there is an error
        :param fn_handle_streaming_chunk: Optional function to execute when we get a chunk in streaming
        :param fn_handle_ids: Optional function to execute when we get a page of ids
        :return: list of resources
        """
        queue: asyncio.Queue[List[str]] = asyncio.Queue()
        chunk: List[str]
        for chunk in chunks:
            await queue.put(chunk)

        async with self.create_http_session() as http:
            tasks = [
                self.get_resources_by_id_from_queue_async(
                    session=http,
                    queue=queue,
                    task_number=taskNumber,
                    fn_handle_batch=fn_handle_batch,
                    fn_handle_error=fn_handle_error,
                    fn_handle_ids=fn_handle_ids,
                    fn_handle_streaming_chunk=fn_handle_streaming_chunk,
                )
                for taskNumber in range(concurrent_requests)
            ]
            for first_completed in asyncio.as_completed(tasks):
                result_list: List[Dict[str, Any]] = await first_completed
            await queue.join()
            return result_list

    # noinspection PyUnusedLocal
    async def get_resources_by_id_from_queue_async(
        self,
        session: ClientSession,
        queue: asyncio.Queue[List[str]],
        task_number: int,
        fn_handle_batch: Optional[HandleBatchFunction],
        fn_handle_error: Optional[HandleErrorFunction],
        fn_handle_ids: Optional[HandleBatchFunction] = None,
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction] = None,
    ) -> List[Dict[str, Any]]:
        """
        Gets resources given a queue


        :param session:
        :param queue: queue to use
        :param task_number:
        :param fn_handle_batch: Optional function to execute on each page of data.  Note that if this is passed we don't
                                return the resources in the response anymore.  If this function returns false then we
                                stop processing any further batches.
        :param fn_handle_error: function that is called when there is an error
        :param fn_handle_streaming_chunk: Optional function to execute when we get a chunk in streaming
        :param fn_handle_ids: Optional function to execute when we get a page of ids
        :return: list of resources
        """
        result: List[Dict[str, Any]] = []
        while not queue.empty():
            try:
                chunk = queue.get_nowait()
                # Notify the queue that the "work item" has been processed.
                queue.task_done()
                if chunk is not None:
                    result_per_chunk: GetResult = await self.get_with_handler_async(
                        session=session,
                        page_number=0,  # this stays at 0 as we're always just loading the first page with id:above
                        ids=chunk,
                        fn_handle_batch=fn_handle_batch,
                        fn_handle_error=fn_handle_error,
                        fn_handle_streaming_chunk=fn_handle_streaming_chunk,
                    )
                    if result_per_chunk:
                        for result_ in result_per_chunk.resources:
                            result.append(result_)
            except Empty:
                break
        return result

    # Yield successive n-sized chunks from l.
    @staticmethod
    def _divide_into_chunks(
        array: List[Any], chunk_size: int
    ) -> Generator[List[str], None, None]:
        """
        Divides a list into a list of chunks


        :param array: array to divide into chunks
        :param chunk_size: size of each chunk
        :return: generator that returns a list of strings
        """
        # looping till length l
        for i in range(0, len(array), chunk_size):
            yield array[i : i + chunk_size]

    def handle_error_wrapper(self) -> HandleErrorFunction:
        """
        Default handler for errors.  Can be replaced by passing in fnError to functions


        """

        async def handle_error_async(
            error: str, response: str, page_number: Optional[int]
        ) -> bool:
            if self._logger:
                self._logger.error(f"page: {page_number} {error}: {response}")
            if self._internal_logger:
                self._internal_logger.error(f"page: {page_number} {error}: {response}")
            return True

        return handle_error_async

    async def get_resources_by_query_and_last_updated_async(
        self,
        *,
        last_updated_start_date: datetime,
        last_updated_end_date: datetime,
        concurrent_requests: int = 10,
        page_size_for_retrieving_resources: int = 100,
        page_size_for_retrieving_ids: int = 10000,
        fn_handle_batch: Optional[HandleBatchFunction] = None,
        fn_handle_error: Optional[HandleErrorFunction] = None,
        fn_handle_ids: Optional[HandleBatchFunction] = None,
        fn_handle_streaming_ids: Optional[HandleStreamingChunkFunction] = None,
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction] = None,
    ) -> List[Dict[str, Any]]:
        """
        Gets results for a query by paging through one day at a time,
            first downloading all the ids and then retrieving resources for each id in parallel


        :param fn_handle_batch: Optional function to execute on each page of data.  Note that if this is passed we don't
                                return the resources in the response anymore.  If this function returns false then we
                                stop processing any further batches.
        :param fn_handle_error: Optional function that is called when there is an error
        :param fn_handle_streaming_ids: Optional function to execute when we get ids in streaming
        :param fn_handle_streaming_chunk: Optional function to execute when we get a chunk in streaming
        :param fn_handle_ids: Optional function to execute when we get a page of ids
        :param last_updated_start_date: Finds the resources updated after this datetime
        :param last_updated_end_date: find resources updated before this datetime
        :param concurrent_requests: number of concurrent requests to make to the server
        :param page_size_for_retrieving_resources: number of resources to download in one batch
        :param page_size_for_retrieving_ids:: number of ids to download in one batch
        """
        return await self.get_resources_by_query_async(
            concurrent_requests=concurrent_requests,
            last_updated_end_date=last_updated_end_date,
            last_updated_start_date=last_updated_start_date,
            page_size_for_retrieving_ids=page_size_for_retrieving_ids,
            page_size_for_retrieving_resources=page_size_for_retrieving_resources,
            fn_handle_error=fn_handle_error,
            fn_handle_batch=fn_handle_batch,
            fn_handle_ids=fn_handle_ids,
            fn_handle_streaming_ids=fn_handle_streaming_ids,
            fn_handle_streaming_chunk=fn_handle_streaming_chunk,
        )

    def get_resources_by_query_and_last_updated(
        self,
        last_updated_start_date: datetime,
        last_updated_end_date: datetime,
        concurrent_requests: int = 10,
        page_size_for_retrieving_resources: int = 100,
        page_size_for_retrieving_ids: int = 10000,
        fn_handle_batch: Optional[HandleBatchFunction] = None,
        fn_handle_error: Optional[HandleErrorFunction] = None,
    ) -> List[Dict[str, Any]]:
        """
        Gets results for a query by paging through one day at a time,
            first downloading all the ids and then retrieving resources for each id in parallel


        :param fn_handle_batch: Optional function to execute on each page of data.  Note that if this is passed we don't
                                return the resources in the response anymore.  If this function returns false then we
                                stop processing any further batches.
        :param fn_handle_error: Optional function that is called when there is an error
        :param last_updated_start_date: find resources updated after this datetime
        :param last_updated_end_date: find resources updated before this datetime
        :param concurrent_requests: number of concurrent requests to make to the server
        :param page_size_for_retrieving_resources: number of resources to download in one batch
        :param page_size_for_retrieving_ids:: number of ids to download in one batch
        """
        return asyncio.run(
            self.get_resources_by_query_and_last_updated_async(
                last_updated_start_date=last_updated_start_date,
                last_updated_end_date=last_updated_end_date,
                concurrent_requests=concurrent_requests,
                page_size_for_retrieving_resources=page_size_for_retrieving_resources,
                page_size_for_retrieving_ids=page_size_for_retrieving_ids,
                fn_handle_batch=fn_handle_batch,
                fn_handle_error=fn_handle_error,
            )
        )

    async def get_resources_by_query_async(
        self,
        last_updated_start_date: Optional[datetime] = None,
        last_updated_end_date: Optional[datetime] = None,
        concurrent_requests: int = 10,
        page_size_for_retrieving_resources: int = 100,
        page_size_for_retrieving_ids: int = 10000,
        fn_handle_batch: Optional[HandleBatchFunction] = None,
        fn_handle_error: Optional[HandleErrorFunction] = None,
        fn_handle_ids: Optional[HandleBatchFunction] = None,
        fn_handle_streaming_ids: Optional[HandleStreamingChunkFunction] = None,
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction] = None,
    ) -> List[Dict[str, Any]]:
        """
        Gets results for a query by first downloading all the ids and then retrieving resources for each id in parallel


        :param fn_handle_batch: Optional function to execute on each page of data.  Note that if this is passed we don't
                                return the resources in the response anymore.  If this function returns false then we
                                stop processing any further batches.
        :param fn_handle_error: function that is called when there is an error
        :param fn_handle_streaming_ids: Optional function to execute when we get ids in streaming
        :param fn_handle_streaming_chunk: Optional function to execute when we get a chunk in streaming
        :param fn_handle_ids: Optional function to execute when we get a page of ids
        :param last_updated_start_date: finds resources updated after this datetime
        :param last_updated_end_date: find resources updated before this datetime
        :param concurrent_requests: number of concurrent requests to make to the server
        :param page_size_for_retrieving_resources: number of resources to download in one batch
        :param page_size_for_retrieving_ids:: number of ids to download in one batch
        """
        start = time.time()
        list_of_ids: List[str] = await self.get_ids_for_query_async(
            concurrent_requests=concurrent_requests,
            last_updated_end_date=last_updated_end_date,
            last_updated_start_date=last_updated_start_date,
            page_size_for_retrieving_ids=page_size_for_retrieving_ids,
            fn_handle_ids=fn_handle_ids,
            fn_handle_streaming_chunk=fn_handle_streaming_ids,
            fn_handle_error=fn_handle_error,
        )
        # now split the ids
        chunks: Generator[List[str], None, None] = self._divide_into_chunks(
            list_of_ids, page_size_for_retrieving_resources
        )
        # chunks_list = list(chunks)
        resources = []

        async def add_resources_to_list(
            resources_: List[Dict[str, Any]], page_number: Optional[int]
        ) -> bool:
            """
            adds resources to a list of resources

            :param resources_:
            :param page_number:
            :return: whether to continue
            """
            end_batch = time.time()
            for resource_ in resources_:
                resources.append(resource_)
            if self._logger:
                self._logger.info(
                    f"Received {len(resources_)} resources (total={len(resources)}/{len(list_of_ids)})"
                    f" in {timedelta(seconds=(end_batch - start))} page={page_number}"
                    f" starting with resource: {resources_[0]['id'] if len(resources_) > 0 else 'none'}"
                )

            return True

        # create a new one to reset all the properties
        self._include_only_properties = None
        self._filters = []

        await self.get_resources_by_id_in_parallel_batches_async(
            concurrent_requests=concurrent_requests,
            chunks=chunks,
            fn_handle_batch=fn_handle_batch or add_resources_to_list,
            fn_handle_error=fn_handle_error or self.handle_error_wrapper(),
            fn_handle_ids=fn_handle_ids,
            fn_handle_streaming_chunk=fn_handle_streaming_chunk,
        )
        return resources

    # noinspection PyUnusedLocal
    async def get_ids_for_query_async(
        self,
        *,
        last_updated_start_date: Optional[datetime] = None,
        last_updated_end_date: Optional[datetime] = None,
        concurrent_requests: int = 10,
        page_size_for_retrieving_ids: int = 10000,
        fn_handle_ids: Optional[HandleBatchFunction] = None,
        fn_handle_batch: Optional[HandleBatchFunction] = None,
        fn_handle_error: Optional[HandleErrorFunction] = None,
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction] = None,
    ) -> List[str]:
        """
        Gets just the ids of the resources matching the query


        :param fn_handle_error:
        :param fn_handle_batch:
        :param last_updated_start_date: (Optional) get ids updated after this date
        :param last_updated_end_date: (Optional) get ids updated before this date
        :param concurrent_requests: number of concurrent requests
        :param page_size_for_retrieving_ids:
        :param fn_handle_streaming_chunk: Optional function to execute when we get a chunk in streaming
        :param fn_handle_ids: Optional function to execute when we get a page of ids
        :return: list of ids
        """
        # get only ids first
        list_of_ids: List[str] = []
        fhir_client = self.include_only_properties(["id"])
        fhir_client = fhir_client.page_size(page_size_for_retrieving_ids)
        output_queue: asyncio.Queue[PagingResult] = asyncio.Queue()

        async def add_to_list(
            resources_: List[Dict[str, Any]], page_number: Optional[int]
        ) -> bool:
            end_batch = time.time()
            assert isinstance(list_of_ids, list)
            assert isinstance(resources_, list)
            for resource_ in resources_:
                list_of_ids.append(resource_["id"])
            if fn_handle_ids:
                await fn_handle_ids(resources_, page_number)
            if self._logger:
                self._logger.info(
                    f"Received {len(resources_)} ids from page {page_number}"
                    f" (total={len(list_of_ids)}) in {timedelta(seconds=end_batch - start)}"
                    f" starting with id: {resources_[0]['id'] if len(resources_) > 0 else 'none'}"
                )

            return True

        # get token first
        await fhir_client.get_access_token_async()
        if last_updated_start_date is not None and last_updated_end_date is not None:
            assert last_updated_end_date >= last_updated_start_date
            greater_than = last_updated_start_date - timedelta(days=1)
            less_than = greater_than + timedelta(days=1)
            last_updated_filter = LastUpdatedFilter(
                less_than=less_than, greater_than=greater_than
            )
            fhir_client = fhir_client.filter([last_updated_filter])
            while greater_than < last_updated_end_date:
                greater_than = greater_than + timedelta(days=1)
                less_than = greater_than + timedelta(days=1)
                if self._logger:
                    self._logger.info(f"===== Processing date {greater_than} =======")
                last_updated_filter.less_than = less_than
                last_updated_filter.greater_than = greater_than
                start = time.time()
                fhir_client._last_page = None  # clean any previous setting
                await fhir_client.get_by_query_in_pages_async(
                    concurrent_requests=concurrent_requests,
                    output_queue=output_queue,
                    fn_handle_batch=add_to_list,
                    fn_handle_error=fn_handle_error or self.handle_error_wrapper(),
                    fn_handle_streaming_chunk=fn_handle_streaming_chunk,
                )
                fhir_client._last_page = None  # clean any previous setting
                end = time.time()
                if self._logger:
                    self._logger.info(
                        f"Runtime processing date is {timedelta(seconds=end - start)} for {len(list_of_ids)} ids"
                    )
        else:
            start = time.time()
            fhir_client._last_page = None  # clean any previous setting
            await fhir_client.get_by_query_in_pages_async(
                concurrent_requests=concurrent_requests,
                output_queue=output_queue,
                fn_handle_batch=add_to_list,
                fn_handle_error=self.handle_error_wrapper(),
                fn_handle_streaming_chunk=fn_handle_streaming_chunk,
            )
            fhir_client._last_page = None  # clean any previous setting
            end = time.time()
            if self._logger:
                self._logger.info(
                    f"Runtime processing date is {timedelta(seconds=end - start)} for {len(list_of_ids)} ids"
                )
        if self._logger:
            self._logger.info(f"====== Received {len(list_of_ids)} ids =======")
        return list_of_ids

    def get_ids_for_query(
        self,
        *,
        last_updated_start_date: Optional[datetime] = None,
        last_updated_end_date: Optional[datetime] = None,
        concurrent_requests: int = 10,
        page_size_for_retrieving_ids: int = 10000,
    ) -> List[str]:
        """
        Gets just the ids of the resources matching the query


        :param last_updated_start_date: (Optional) get ids updated after this date
        :param last_updated_end_date: (Optional) get ids updated before this date
        :param concurrent_requests:
        :param page_size_for_retrieving_ids:
        :return: list of ids
        """
        return asyncio.run(
            self.get_ids_for_query_async(
                last_updated_start_date=last_updated_start_date,
                last_updated_end_date=last_updated_end_date,
                concurrent_requests=concurrent_requests,
                page_size_for_retrieving_ids=page_size_for_retrieving_ids,
            )
        )

    def get_resources_by_query(
        self,
        last_updated_start_date: Optional[datetime] = None,
        last_updated_end_date: Optional[datetime] = None,
        concurrent_requests: int = 10,
        page_size_for_retrieving_resources: int = 100,
        page_size_for_retrieving_ids: int = 10000,
        fn_handle_batch: Optional[HandleBatchFunction] = None,
        fn_handle_error: Optional[HandleErrorFunction] = None,
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction] = None,
    ) -> List[Dict[str, Any]]:
        """
        Gets results for a query by first downloading all the ids and then retrieving resources for each id in parallel


        :param fn_handle_streaming_chunk:
        :param fn_handle_batch: Optional function to execute on each page of data.  Note that if this is passed we don't
                                return the resources in the response anymore.  If this function returns false then we
                                stop processing any further batches.
        :param fn_handle_error: function that is called when there is an error
        :param last_updated_start_date: (Optional) get ids updated after this date
        :param last_updated_end_date: (Optional) get ids updated before this date
        :param concurrent_requests: number of concurrent requests to make to the server
        :param page_size_for_retrieving_resources: number of resources to download in one batch
        :param page_size_for_retrieving_ids:: number of ids to download in one batch
        """
        return asyncio.run(
            self.get_resources_by_query_async(
                last_updated_start_date=last_updated_start_date,
                last_updated_end_date=last_updated_end_date,
                concurrent_requests=concurrent_requests,
                page_size_for_retrieving_resources=page_size_for_retrieving_resources,
                page_size_for_retrieving_ids=page_size_for_retrieving_ids,
                fn_handle_batch=fn_handle_batch,
                fn_handle_error=fn_handle_error,
                fn_handle_streaming_chunk=fn_handle_streaming_chunk,
            )
        )

    # noinspection PyPep8Naming
    async def simulate_graph_async(
        self,
        *,
        id_: Union[List[str], str],
        graph_json: Dict[str, Any],
        contained: bool,
        concurrent_requests: int = 1,
        separate_bundle_resources: bool = False,
        restrict_to_scope: Optional[str] = None,
        restrict_to_resources: Optional[List[str]] = None,
        restrict_to_capability_statement: Optional[str] = None,
        retrieve_and_restrict_to_capability_statement: Optional[bool] = None,
        ifModifiedSince: Optional[datetime] = None,
        eTag: Optional[str] = None,
    ) -> FhirGetResponse:
        """
        Simulates the $graph query on the FHIR server


        :param separate_bundle_resources:
        :param id_: single id or list of ids (ids can be comma separated too)
        :param concurrent_requests:
        :param graph_json: definition of a graph to execute
        :param contained: whether we should return the related resources as top level list or nest them inside their
                            parent resources in a contained property
        :param restrict_to_scope: Optional scope to restrict to
        :param restrict_to_resources: Optional list of resources to restrict to
        :param restrict_to_capability_statement: Optional capability statement to restrict to
        :param retrieve_and_restrict_to_capability_statement: Optional capability statement to retrieve and restrict to
        :param ifModifiedSince: Optional datetime to use for If-Modified-Since header
        :param eTag: Optional ETag to use for If-None-Match header
        :return: FhirGetResponse
        """
        if contained:
            if not self._additional_parameters:
                self._additional_parameters = []
            self._additional_parameters.append("contained=true")

        return await self.process_simulate_graph_async(
            id_=id_,
            graph_json=graph_json,
            contained=contained,
            concurrent_requests=concurrent_requests,
            separate_bundle_resources=separate_bundle_resources,
            restrict_to_scope=restrict_to_scope,
            restrict_to_resources=restrict_to_resources,
            restrict_to_capability_statement=restrict_to_capability_statement,
            retrieve_and_restrict_to_capability_statement=retrieve_and_restrict_to_capability_statement,
            ifModifiedSince=ifModifiedSince,
            eTag=eTag,
            url=self._url,
            expand_fhir_bundle=self._expand_fhir_bundle,
            logger=self._logger,
            auth_scopes=self._auth_scopes,
        )
