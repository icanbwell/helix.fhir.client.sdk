from __future__ import annotations
import asyncio
import base64
import json
import logging
import time
from asyncio import Future
from datetime import datetime, timedelta
from logging import Logger
from queue import Empty
from threading import Lock
from typing import (
    Dict,
    Optional,
    List,
    Union,
    Any,
    Callable,
    Generator,
    AsyncGenerator,
    Coroutine,
)
from urllib import parse

import aiohttp
import requests
from aiohttp import ClientSession, ClientResponse, ClientPayloadError
from furl import furl
from helix_fhir_client_sdk.exceptions.fhir_sender_exception import FhirSenderException
from helix_fhir_client_sdk.filters.base_filter import BaseFilter
from helix_fhir_client_sdk.filters.last_updated_filter import LastUpdatedFilter
from helix_fhir_client_sdk.filters.sort_field import SortField
from helix_fhir_client_sdk.graph.graph_definition import GraphDefinition
from helix_fhir_client_sdk.loggers.fhir_logger import FhirLogger
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse
from helix_fhir_client_sdk.responses.paging_result import PagingResult
from helix_fhir_client_sdk.validators.async_fhir_validator import AsyncFhirValidator
from helix_fhir_client_sdk.well_known_configuration import (
    WellKnownConfigurationCacheEntry,
)
from requests.adapters import BaseAdapter

# from urllib3 import Retry  # type: ignore

HandleBatchFunction = Callable[[List[Dict[str, Any]], Optional[int]], bool]
HandleErrorFunction = Callable[[str, str, Optional[int]], bool]


class AsyncFhirClient:
    """
        Class used to call FHIR server (uses async and parallel execution to speed up)
        """

    _time_to_live_in_secs_for_cache: int = 10 * 60

    # caches result from calls to well known configuration
    #   key is host name of fhir server, value is  auth_server_url
    _well_known_configuration_cache: Dict[str, WellKnownConfigurationCacheEntry] = {}

    # used to lock access to above cache
    _well_known_configuration_cache_lock: Lock = Lock()

    def __init__(self) -> None:
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
        self._internal_logger: Logger = logging.getLogger("FhirClient")
        self._internal_logger.setLevel(logging.INFO)
        self._obj_id: Optional[str] = None
        self._include_total: bool = False
        self._filters: List[BaseFilter] = []
        self._expand_fhir_bundle: bool = True

        self._stop_processing: bool = False
        self._authentication_token_lock: Lock = Lock()
        self._last_page: Optional[int] = None
        self._last_page_lock: Lock = Lock()

    def action(self, action: str) -> "AsyncFhirClient":
        """
        :param action: (Optional) do an action e.g., $everything
        """
        self._action = action
        return self

    def action_payload(self, action_payload: Dict[str, Any]) -> "AsyncFhirClient":
        """
        :param action_payload: (Optional) if action such as $graph needs a http payload
        """
        self._action_payload = action_payload
        return self

    def resource(self, resource: str) -> "AsyncFhirClient":
        """
        :param resource: what FHIR resource to retrieve
        """
        self._resource = resource
        return self

    def id_(self, id_: Union[List[str], str]) -> "AsyncFhirClient":
        self._id = id_
        return self

    def url(self, url: str) -> "AsyncFhirClient":
        """
        :param url: server to call for FHIR
        """
        self._url = url
        return self

    def validation_server_url(self, validation_server_url: str) -> "AsyncFhirClient":
        """
        :param validation_server_url: server to call for FHIR validation
        """
        self._validation_server_url = validation_server_url
        return self

    def additional_parameters(
        self, additional_parameters: List[str]
    ) -> "AsyncFhirClient":
        """
        :param additional_parameters: Any additional parameters to send with request
        """
        self._additional_parameters = additional_parameters
        return self

    def filter_by_resource(self, filter_by_resource: str) -> "AsyncFhirClient":
        """
        :param filter_by_resource: filter the resource by this. e.g., /Condition?Patient=1
                (resource=Condition, filter_by_resource=Patient)
        """
        self._filter_by_resource = filter_by_resource
        return self

    def filter_parameter(self, filter_parameter: str) -> "AsyncFhirClient":
        """
        :param filter_parameter: Instead of requesting ?patient=1,
                do ?subject:Patient=1 (if filter_parameter is subject)
        """
        self._filter_parameter = filter_parameter
        return self

    def include_only_properties(
        self, include_only_properties: List[str]
    ) -> "AsyncFhirClient":
        """
        :param include_only_properties: includes only these properties
        """
        self._include_only_properties = include_only_properties
        return self

    def page_number(self, page_number: int) -> "AsyncFhirClient":
        """
        :param page_number: page number to load
        """
        self._page_number = page_number
        return self

    def page_size(self, page_size: int) -> "AsyncFhirClient":
        """
        :param page_size: (Optional) use paging and get this many items in each page
        """

        self._page_size = page_size
        return self

    def last_updated_after(self, last_updated_after: datetime) -> "AsyncFhirClient":
        """
        :param last_updated_after: (Optional) Only get records newer than this
        """
        self._last_updated_after = last_updated_after
        return self

    def last_updated_before(self, last_updated_before: datetime) -> "AsyncFhirClient":
        """
        :param last_updated_before: (Optional) Only get records older than this
        """
        self._last_updated_before = last_updated_before
        return self

    def sort_fields(self, sort_fields: List[SortField]) -> "AsyncFhirClient":
        """
        :param sort_fields: sort by fields in the resource
        """
        self._sort_fields = sort_fields
        return self

    def auth_server_url(self, auth_server_url: str) -> "AsyncFhirClient":
        """
        :param auth_server_url: server url to call to get the authentication token
        """
        self._auth_server_url = auth_server_url
        return self

    def auth_scopes(self, auth_scopes: List[str]) -> "AsyncFhirClient":
        """
        :param auth_scopes: list of scopes to request permission for e.g., system/AllergyIntolerance.read
        """
        assert isinstance(auth_scopes, list), f"{type(auth_scopes)} is not a list"
        self._auth_scopes = auth_scopes
        return self

    def login_token(self, login_token: str) -> "AsyncFhirClient":
        """
        :param login_token: login token to use
        """
        self._login_token = login_token
        return self

    def client_credentials(
        self, client_id: str, client_secret: str
    ) -> "AsyncFhirClient":
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

    def logger(self, logger: FhirLogger) -> "AsyncFhirClient":
        """
        Logger to use for logging calls to the FHIR server


        :param logger: logger
        """
        self._logger = logger
        return self

    def adapter(self, adapter: BaseAdapter) -> "AsyncFhirClient":
        """
        Http Adapter to use for calling the FHIR server


        :param adapter: adapter
        """
        self._adapter = adapter
        return self

    def limit(self, limit: int) -> "AsyncFhirClient":
        """
        Limit the results


        :param limit: Limit results to this count
        """
        self._limit = limit
        return self

    @property
    async def access_token(self) -> Optional[str]:
        """
        Gets current access token


        :return: access token if any
        """
        # if we have an auth server url but no access token then get access token
        if self._login_token and not self._auth_server_url:
            # try to get auth_server_url from well known configuration
            self._auth_server_url = (
                await self._get_auth_server_url_from_well_known_configuration()
            )
            if self._auth_server_url:
                logging.info(
                    f"Received {self._auth_server_url} from well_known configuration of server: {self._url}"
                )
        if self._auth_server_url and not self._access_token:
            assert (
                self._login_token
            ), "login token must be present if auth_server_url is set"
            async with self.create_http_session() as http:
                self._access_token = await self.authenticate(
                    http=http,
                    auth_server_url=self._auth_server_url,
                    auth_scopes=self._auth_scopes,
                    login_token=self._login_token,
                )
        return self._access_token

    @access_token.setter
    def access_token(self, value: str) -> None:
        """
        Sets access token


        :param value: value to set access token to
        """
        self._access_token = value

    def set_access_token(self, value: str) -> "AsyncFhirClient":
        """
        Sets access token


        :param value: access token
        """
        self._access_token = value
        return self

    async def delete(self) -> ClientResponse:
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

            # set access token in request if present
            if await self.access_token:
                headers["Authorization"] = f"Bearer {await self.access_token}"

            # actually make the request
            response: ClientResponse = await http.delete(
                full_uri.tostr(), headers=headers
            )
            if response.ok:
                if self._logger:
                    self._logger.info(f"Successfully deleted: {full_uri}")

            return response

    def separate_bundle_resources(
        self, separate_bundle_resources: bool
    ) -> "AsyncFhirClient":
        """
        Set flag to separate bundle resources


        :param separate_bundle_resources:
        """
        self._separate_bundle_resources = separate_bundle_resources
        return self

    def expand_fhir_bundle(self, expand_fhir_bundle: bool) -> "AsyncFhirClient":
        """
        Set flag to expand the FHIR bundle into a list of resources. If false then we don't un bundle the response


        :param expand_fhir_bundle: whether to just return the result as a FHIR bundle
        """
        self._expand_fhir_bundle = expand_fhir_bundle
        return self

    async def get(self) -> FhirGetResponse:
        """
        Issues a GET call
        """
        ids: Optional[List[str]] = None
        if self._id:
            ids = self._id if isinstance(self._id, list) else [self._id]
        # actually make the request
        async with self.create_http_session() as http:
            return await self._get_with_session(session=http, ids=ids)

    async def _get_with_session(
        self,
        session: Optional[ClientSession],
        page_number: Optional[int] = None,
        ids: Optional[List[str]] = None,
    ) -> FhirGetResponse:
        """
        Issues a GET call
        """
        assert self._url, "No FHIR server url was set"
        assert self._resource, "No Resource was set"
        retries: int = 2
        while retries >= 0:
            retries = retries - 1
            # create url and query to request from FHIR server
            resources: str = ""
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
                        ] = ids[0]
                    else:
                        # ?patient=27384972
                        full_uri.args[self._filter_by_resource.lower()] = ids[0]
                else:
                    if len(ids) == 1 and not self._obj_id:
                        full_uri /= ids
                    else:
                        full_uri.args["id"] = ",".join(ids)
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

            # add any sort fields
            if self._sort_fields is not None:
                full_uri.args["_sort"] = ",".join([str(s) for s in self._sort_fields])

                # create full url by adding on any query parameters
            full_url: str = full_uri.url
            if self._additional_parameters:
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

            # set up headers
            payload: Dict[str, str] = (
                self._action_payload if self._action_payload else {}
            )
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/fhir+json",
                "Accept-Encoding": "gzip,deflate",
            }

            # set access token in request if present
            if await self.access_token:
                headers["Authorization"] = f"Bearer {await self.access_token}"

            # actually make the request
            if session is None:
                http = self.create_http_session()
            else:
                http = session
            response: ClientResponse = await self._send_fhir_request(
                http, full_url, headers, payload
            )
            # if request is ok (200) then return the data
            if response.ok:
                if self._logger:
                    self._logger.info(f"Successfully retrieved: {full_url}")

                total_count: int = 0
                # noinspection PyBroadException
                try:
                    text = await response.text()
                except ClientPayloadError as e:
                    # do a retry
                    if self._logger:
                        self._logger.error(f"{e}: {response.headers}")
                    continue
                if len(text) > 0:
                    response_json: Dict[str, Any] = json.loads(text)
                    # see if this is a Resource Bundle and un-bundle it
                    if (
                        self._expand_fhir_bundle
                        and "resourceType" in response_json
                        and response_json["resourceType"] == "Bundle"
                    ):
                        if "total" in response_json:
                            total_count = int(response_json["total"])
                        if "entry" in response_json:
                            entries: List[Dict[str, Any]] = response_json["entry"]
                            entry: Dict[str, Any]
                            resources_list: List[Dict[str, Any]] = []
                            for entry in entries:
                                if "resource" in entry:
                                    if self._separate_bundle_resources:
                                        if self._action != "$graph":
                                            raise Exception(
                                                "only $graph action with _separate_bundle_resources=True"
                                                " is supported at this moment"
                                            )
                                        resources_dict: Dict[
                                            str, List[Any]
                                        ] = {}  # {resource type: [data]}}
                                        # iterate through the entry list
                                        # have to split these here otherwise when Spark loads them it can't handle
                                        # that items in the entry array can have different types
                                        resource_type: str = str(
                                            entry["resource"]["resourceType"]
                                        ).lower()
                                        parent_resource: Dict[str, Any] = entry[
                                            "resource"
                                        ]
                                        resources_dict[resource_type] = [
                                            parent_resource
                                        ]
                                        # $graph returns "contained" if there is any related resources
                                        if "contained" in entry["resource"]:
                                            contained = parent_resource.pop("contained")
                                            for contained_entry in contained:
                                                resource_type = str(
                                                    contained_entry["resourceType"]
                                                ).lower()
                                                if resource_type not in resources_dict:
                                                    resources_dict[resource_type] = []

                                                resources_dict[resource_type].append(
                                                    contained_entry
                                                )
                                        resources_list.append(resources_dict)

                                    else:
                                        resources_list.append(entry["resource"])

                            resources = json.dumps(resources_list)
                    else:
                        resources = text
                return FhirGetResponse(
                    url=full_url,
                    responses=resources,
                    error=None,
                    access_token=self._access_token,
                    total_count=total_count,
                )
            elif response.status == 404:  # not found
                if self._logger:
                    self._logger.error(f"resource not found! {full_url}")
                return FhirGetResponse(
                    url=full_url,
                    responses=await response.text(),
                    error=f"{response.status}",
                    access_token=self._access_token,
                    total_count=0,
                )
            elif response.status == 502 or response.status == 504:  # time out
                if retries >= 0:
                    continue
            elif (
                response.status == 403 or response.status == 401
            ):  # forbidden or unauthorized
                if retries >= 0:
                    assert (
                        self._auth_server_url
                    ), f"{response.status} received from server but no auth_server_url was specified to use"
                    assert (
                        self._login_token
                    ), f"{response.status} received from server but no login_token was specified to use"
                    self._access_token = await self.authenticate(
                        http=http,
                        auth_server_url=self._auth_server_url,
                        auth_scopes=self._auth_scopes,
                        login_token=self._login_token,
                    )
                    # try again
                    continue
                else:
                    # out of retries so just fail now
                    return FhirGetResponse(
                        url=full_url,
                        responses=await response.text(),
                        error=f"{response.status}",
                        access_token=self._access_token,
                        total_count=0,
                    )
            else:
                # some unexpected error
                if self._logger:
                    self._logger.error(
                        f"Fhir Receive failed [{response.status}]: {full_url} "
                    )
                error_text: str = await response.text()
                if self._logger:
                    self._logger.error(error_text)
                resources = error_text
                return FhirGetResponse(
                    url=full_url,
                    responses=await response.text(),
                    access_token=self._access_token,
                    error=f"{response.status}",
                    total_count=0,
                )
        raise Exception("Could not talk to FHIR server after multiple tries")

    async def _send_fhir_request(
        self,
        http: ClientSession,
        full_url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
    ) -> ClientResponse:
        """
        Sends a request to the server


        :param http: session to use
        :param full_url:
        :param headers:
        :param payload:
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
            if self._logger:
                self._logger.info(
                    f"sending a get: {full_url} with client_id={self._client_id} and scopes={self._auth_scopes}"
                )
            self._internal_logger.info(
                f"sending a get: {full_url} with client_id={self._client_id} and scopes={self._auth_scopes}"
            )
            return await http.get(full_url, headers=headers, data=payload)

    @staticmethod
    def create_http_session() -> ClientSession:
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
        session: ClientSession = aiohttp.ClientSession(
            headers={"Connection": "keep-alive"}
        )
        return session

    async def get_with_handler(
        self,
        session: Optional[ClientSession],
        page_number: Optional[int],
        ids: Optional[List[str]],
        fn_handle_batch: Optional[HandleBatchFunction],
        fn_handle_error: Optional[HandleErrorFunction],
    ) -> List[Dict[str, Any]]:
        result = await self._get_with_session(
            session=session, page_number=page_number, ids=ids
        )
        if result.error:
            if fn_handle_error:
                fn_handle_error(result.error, result.responses, page_number)
        elif not result.error and bool(result.responses):
            result_list: List[Dict[str, Any]] = json.loads(result.responses)
            if fn_handle_batch:
                if fn_handle_batch(result_list, page_number) is False:
                    self._stop_processing = True
            return result_list
        return []

    async def get_page_by_query(
        self,
        session: Optional[ClientSession],
        start_page: int,
        increment: int,
        output_queue: asyncio.Queue[PagingResult],
        fn_handle_batch: Optional[HandleBatchFunction],
        fn_handle_error: Optional[HandleErrorFunction],
    ) -> List[PagingResult]:
        page_number: int = start_page
        result: List[PagingResult] = []
        while (
            not self._last_page and not self._last_page == 0
        ) or page_number < self._last_page:
            result_for_page: List[Dict[str, Any]] = await self.get_with_handler(
                session=session,
                page_number=page_number,
                ids=None,
                fn_handle_batch=fn_handle_batch,
                fn_handle_error=fn_handle_error,
            )
            if result_for_page and len(result_for_page) > 0:
                paging_result = PagingResult(
                    resources=result_for_page, page_number=page_number
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
            page_number = page_number + increment
        return result

    async def get_tasks(
        self,
        concurrent_requests: int,
        output_queue: asyncio.Queue[PagingResult],
        fn_handle_batch: Optional[HandleBatchFunction],
        fn_handle_error: Optional[HandleErrorFunction],
        http: ClientSession,
    ) -> AsyncGenerator[Coroutine[Any, Any, List[PagingResult]], None]:
        for taskNumber in range(concurrent_requests):
            yield (
                self.get_page_by_query(
                    session=http,
                    start_page=taskNumber,
                    increment=concurrent_requests,
                    output_queue=output_queue,
                    fn_handle_batch=fn_handle_batch,
                    fn_handle_error=fn_handle_error,
                )
            )

    async def get_by_query_in_pages(
        self,
        concurrent_requests: int,
        output_queue: asyncio.Queue[PagingResult],
        fn_handle_batch: Optional[HandleBatchFunction],
        fn_handle_error: Optional[HandleErrorFunction],
    ) -> FhirGetResponse:
        """
        Retrieves the data in batches (using paging) to reduce load on the FHIR server and to reduce network traffic

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
                    async for task in self.get_tasks(
                        http=http,
                        output_queue=output_queue,
                        concurrent_requests=concurrent_requests,
                        fn_handle_batch=fn_handle_batch,
                        fn_handle_error=fn_handle_error,
                    )
                ]
            ):
                result_list: List[PagingResult] = await first_completed
                for resources in [r.resources for r in result_list]:
                    resources_list.extend(resources)

            return FhirGetResponse(
                self._url,
                responses=json.dumps(resources_list),
                error="",
                access_token=self._access_token,
                total_count=len(resources_list),
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

    async def authenticate(
        self,
        http: ClientSession,
        auth_server_url: str,
        auth_scopes: Optional[List[str]],
        login_token: str,
    ) -> Optional[str]:
        """
        Authenticates with an OAuth Provider


        :param http: http session
        :param auth_server_url: url to auth server /token endpoint
        :param auth_scopes: list of scopes to request
        :param login_token: login token to use for authenticating
        :return: access token
        """
        assert auth_server_url
        assert auth_scopes
        with self._authentication_token_lock:
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

            self._internal_logger.debug(
                f"Authenticating with {auth_server_url} with client_id={self._client_id} for scopes={auth_scopes}"
            )

            response: ClientResponse = await http.request(
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

    async def merge(self, json_data_list: List[str],) -> FhirMergeResponse:
        """
        Calls $merge function on FHIR server


        :param json_data_list: list of resources to send
        """
        assert self._url, "No FHIR server url was set"
        assert isinstance(json_data_list, list), "This function requires a list"

        self._internal_logger.debug(
            f"Calling $merge on {self._url} with client_id={self._client_id} and scopes={self._auth_scopes}"
        )

        retries: int = 2
        while retries >= 0:
            retries = retries - 1
            full_uri: furl = furl(self._url)
            assert self._resource
            full_uri /= self._resource
            headers = {"Content-Type": "application/fhir+json"}
            responses: List[Dict[str, Any]] = []
            async with self.create_http_session() as http:
                # set access token in request if present
                if await self.access_token:
                    headers["Authorization"] = f"Bearer {await self.access_token}"

                try:
                    resource_json_list: List[Dict[str, Any]] = [
                        json.loads(json_data) for json_data in json_data_list
                    ]
                    if self._validation_server_url:
                        resource_json: Dict[str, Any]
                        for resource_json in resource_json_list:
                            await AsyncFhirValidator.validate_fhir_resource(
                                http=http,
                                json_data=json.dumps(resource_json),
                                resource_name=self._resource,
                                validation_server_url=self._validation_server_url,
                            )

                    json_payload: str = json.dumps(resource_json_list)
                    # json_payload_bytes: str = json_payload
                    json_payload_bytes: bytes = json_payload.encode("utf-8")
                    obj_id = 1  # TODO: remove this once the node fhir accepts merge without a parameter
                    assert obj_id
                    resource_uri = full_uri.copy()
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
                        if response and response.ok:
                            # logging does not work in UDFs since they run on nodes
                            # if progress_logger:
                            #     progress_logger.write_to_log(
                            #         f"Posted to {resource_uri.url}: {json_data}"
                            #     )
                            # check if response is json
                            response_text = await response.text()
                            if response_text:
                                try:
                                    responses = json.loads(response_text)
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
                                self._access_token = await self.authenticate(
                                    http=http,
                                    auth_server_url=self._auth_server_url,
                                    auth_scopes=self._auth_scopes,
                                    login_token=self._login_token,
                                )
                                # try again
                                continue
                            else:
                                # out of retries so just fail now
                                response.raise_for_status()
                        else:
                            self._internal_logger.info(
                                f"response for {full_uri.tostr()}: {response.status}"
                            )
                            response.raise_for_status()
                    except requests.exceptions.HTTPError as e:
                        raise FhirSenderException(
                            url=resource_uri.url,
                            json_data=json_payload,
                            response_text=await response.text() if response else "",
                            response_status_code=response.status if response else None,
                            exception=e,
                            message=f"HttpError: {e}",
                        ) from e
                    except Exception as e:
                        raise FhirSenderException(
                            url=resource_uri.url,
                            json_data=json_payload,
                            response_text=await response.text() if response else "",
                            response_status_code=response.status if response else None,
                            exception=e,
                            message=f"Unknown Error: {e}",
                        ) from e

                except AssertionError as e:
                    if self._logger:
                        self._logger.error(
                            Exception(
                                f"Assertion: FHIR send failed: {str(e)} for resource: {json_data_list}"
                            )
                        )
                return FhirMergeResponse(
                    url=self._url or "",
                    responses=responses,
                    error=None,
                    access_token=self._access_token,
                )

        raise Exception("Could not talk to FHIR server after multiple tries")

    async def _get_auth_server_url_from_well_known_configuration(self) -> Optional[str]:
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
            response: ClientResponse = await http.get(full_uri.tostr())
            text_ = await response.text()
            if response and response.ok and text_:
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

    async def graph(
        self,
        *,
        graph_definition: GraphDefinition,
        contained: bool,
        process_in_batches: Optional[bool] = None,
        fn_handle_batch: Optional[HandleBatchFunction] = None,
        fn_handle_error: Optional[HandleErrorFunction] = None,
        concurrent_requests: int = 1,
    ) -> FhirGetResponse:
        """
        Executes the $graph query on the FHIR server


        :param fn_handle_error:
        :param concurrent_requests:
        :param graph_definition: definition of a graph to execute
        :param contained: whether we should return the related resources as top level list or nest them inside their
                            parent resources in a contained property
        :param process_in_batches: whether to process in batches of size page_size
        :param fn_handle_batch: Optional function to execute on each page of data.  Note that if this is passed we don't
                                return the resources in the response anymore.  If this function returns false then we
                                stop processing any further batches.
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
        self._obj_id = "1"  # this is needed because the $graph endpoint requires an id
        output_queue: asyncio.Queue[PagingResult] = asyncio.Queue()
        async with self.create_http_session() as http:
            return (
                await self._get_with_session(session=http)
                if not process_in_batches
                else await self.get_by_query_in_pages(
                    concurrent_requests=concurrent_requests,
                    output_queue=output_queue,
                    fn_handle_error=fn_handle_error,
                    fn_handle_batch=fn_handle_batch,
                )
            )

    def include_total(self, include_total: bool) -> "AsyncFhirClient":
        """
        Whether to ask the server to include the total count in the result

        :param include_total: whether to include total count
        """
        self._include_total = include_total
        return self

    def filter(self, filter_: List[BaseFilter]) -> "AsyncFhirClient":
        """
        Allows adding in a custom filters that derives from BaseFilter


        :param filter_: list of custom filter instances that derives from BaseFilter.
        """
        assert isinstance(filter_, list), "This function requires a list"
        self._filters.extend(filter_)
        return self

    async def update(self, json_data: str) -> ClientResponse:
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

            # set access token in request if present
            if await self.access_token:
                headers["Authorization"] = f"Bearer {await self.access_token}"

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
            if response.ok:
                if self._logger:
                    self._logger.info(f"Successfully updated: {full_uri}")

            return response

    async def get_resources_by_id_in_parallel_batches(
        self,
        concurrent_requests: int,
        chunks: Generator[List[str], None, None],
        fn_handle_batch: Optional[HandleBatchFunction],
        fn_handle_error: Optional[HandleErrorFunction],
    ) -> List[Dict[str, Any]]:
        queue: asyncio.Queue[List[str]] = asyncio.Queue()
        chunk: List[str]
        for chunk in chunks:
            await queue.put(chunk)

        async with self.create_http_session() as http:
            tasks = [
                self.get_resources_by_id(
                    session=http,
                    queue=queue,
                    task_number=taskNumber,
                    fn_handle_batch=fn_handle_batch,
                    fn_handle_error=fn_handle_error,
                )
                for taskNumber in range(concurrent_requests)
            ]
            for first_completed in asyncio.as_completed(tasks):
                result_list: List[Dict[str, Any]] = await first_completed
            await queue.join()
            return result_list

    async def get_resources_by_id(
        self,
        session: ClientSession,
        queue: asyncio.Queue[List[str]],
        task_number: int,
        fn_handle_batch: Optional[HandleBatchFunction],
        fn_handle_error: Optional[HandleErrorFunction],
    ) -> List[Dict[str, Any]]:

        result: List[Dict[str, Any]] = []
        while not queue.empty():
            try:
                chunk = queue.get_nowait()
                # Notify the queue that the "work item" has been processed.
                queue.task_done()
                if chunk is not None:
                    result_per_chunk: List[
                        Dict[str, Any]
                    ] = await self.get_with_handler(
                        session=session,
                        page_number=0,
                        ids=chunk,
                        fn_handle_batch=fn_handle_batch,
                        fn_handle_error=fn_handle_error,
                    )
                    if result_per_chunk:
                        result.extend(result_per_chunk)
            except Empty:
                break
        return result

    # Yield successive n-sized chunks from l.
    @staticmethod
    def divide_into_chunks(
        array: List[Any], chunk_size: int
    ) -> Generator[List[str], None, None]:
        # looping till length l
        for i in range(0, len(array), chunk_size):
            yield array[i : i + chunk_size]

    def handle_error(
        self, error: str, response: str, page_number: Optional[int]
    ) -> bool:
        if self._logger:
            self._logger.error(f"{error}: {response}")
        if self._internal_logger:
            self._internal_logger.error(f"{error}: {response}")
        return True

    async def get_resources_by_query_and_last_updated(
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
        :param fn_handle_error: Optional function to call when there is an error
        :param fn_handle_batch: Optional function to call when a batch is downloaded
        :param last_updated_start_date: find resources updated after this datetime
        :param last_updated_end_date: find resources updated before this datetime
        :param concurrent_requests: number of concurrent requests to make to the server
        :param page_size_for_retrieving_resources: number of resources to download in one batch
        :param page_size_for_retrieving_ids:: number of ids to download in one batch
        """
        return await self.get_resources_by_query(
            concurrent_requests=concurrent_requests,
            last_updated_end_date=last_updated_end_date,
            last_updated_start_date=last_updated_start_date,
            page_size_for_retrieving_ids=page_size_for_retrieving_ids,
            page_size_for_retrieving_resources=page_size_for_retrieving_resources,
            fn_handle_error=fn_handle_error,
            fn_handle_batch=fn_handle_batch,
        )

    async def get_resources_by_query(
        self,
        last_updated_start_date: Optional[datetime] = None,
        last_updated_end_date: Optional[datetime] = None,
        concurrent_requests: int = 10,
        page_size_for_retrieving_resources: int = 100,
        page_size_for_retrieving_ids: int = 10000,
        fn_handle_batch: Optional[HandleBatchFunction] = None,
        fn_handle_error: Optional[HandleErrorFunction] = None,
    ) -> List[Dict[str, Any]]:
        """
        Gets results for a query by first downloading all the ids and then retrieving resources for each id in parallel
        :param fn_handle_error: Optional function to call when there is an error
        :param fn_handle_batch: Optional function to call when a batch is downloaded
        :param last_updated_start_date: find resources updated after this datetime
        :param last_updated_end_date: find resources updated before this datetime
        :param concurrent_requests: number of concurrent requests to make to the server
        :param page_size_for_retrieving_resources: number of resources to download in one batch
        :param page_size_for_retrieving_ids:: number of ids to download in one batch
        """
        # get only ids first
        fhir_client = self.include_only_properties(["id"])
        fhir_client = fhir_client.page_size(page_size_for_retrieving_ids)

        list_of_ids: List[str] = []
        output_queue: asyncio.Queue[PagingResult] = asyncio.Queue()

        def add_to_list(
            resources_: List[Dict[str, Any]], page_number: Optional[int]
        ) -> bool:
            end_batch = time.time()
            list_of_ids.extend([resource_["id"] for resource_ in resources_])
            if self._logger:
                self._logger.info(
                    f"Received {len(resources_)} ids from page {page_number}"
                    f" (total={len(list_of_ids)}) in {timedelta(seconds=end_batch - start)}"
                    f" starting with id: {resources_[0]['id'] if len(resources_) > 0 else 'none'}"
                )

            return True

        # get token first
        await fhir_client.access_token

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
                await fhir_client.get_by_query_in_pages(
                    concurrent_requests=concurrent_requests,
                    output_queue=output_queue,
                    fn_handle_batch=add_to_list,
                    fn_handle_error=self.handle_error,
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
            await fhir_client.get_by_query_in_pages(
                concurrent_requests=concurrent_requests,
                output_queue=output_queue,
                fn_handle_batch=add_to_list,
                fn_handle_error=self.handle_error,
            )
            fhir_client._last_page = None  # clean any previous setting
            end = time.time()
            if self._logger:
                self._logger.info(
                    f"Runtime processing date is {timedelta(seconds=end - start)} for {len(list_of_ids)} ids"
                )

        if self._logger:
            self._logger.info(f"====== Received {len(list_of_ids)} ids =======")
        # now split the ids
        chunks: Generator[List[str], None, None] = self.divide_into_chunks(
            list_of_ids, page_size_for_retrieving_resources
        )
        # chunks_list = list(chunks)
        resources = []

        def add_resources_to_list(
            resources_: List[Dict[str, Any]], page_number: Optional[int]
        ) -> bool:
            end_batch = time.time()
            resources.extend([resource_ for resource_ in resources_])
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
        await fhir_client.get_resources_by_id_in_parallel_batches(
            concurrent_requests=concurrent_requests,
            chunks=chunks,
            fn_handle_batch=fn_handle_batch or add_resources_to_list,
            fn_handle_error=fn_handle_error or self.handle_error,
        )
        return resources

    async def get_in_batches(
        self, fn_handle_batch: Optional[Callable[[List[Dict[str, Any]]], bool]]
    ) -> FhirGetResponse:
        """
        Retrieves the data in batches (using paging) to reduce load on the FHIR server and to reduce network traffic

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
        resources_list: List[Dict[str, Any]] = []
        while True:
            result: FhirGetResponse = await self.get()
            if not result.error and bool(result.responses):
                result_list: List[Dict[str, Any]] = json.loads(result.responses)
                if len(result_list) == 0:
                    break
                if fn_handle_batch:
                    if fn_handle_batch(result_list) is False:
                        break
                else:
                    resources_list.extend(result_list)
                if self._limit and self._limit > 0:
                    if (self._page_number * self._page_size) > self._limit:
                        break
                self._page_number += 1
            else:
                break
        return FhirGetResponse(
            self._url,
            responses=json.dumps(resources_list),
            error=result.error,
            access_token=self._access_token,
            total_count=result.total_count,
        )
