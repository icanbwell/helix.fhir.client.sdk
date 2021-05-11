import base64
import json
import logging
from datetime import datetime
from threading import Lock
from typing import Dict, Optional, List, Union, Any, NamedTuple
from urllib import parse

import requests
from furl import furl
from requests import Response, Session
from requests.adapters import HTTPAdapter, BaseAdapter
from urllib3 import Retry  # type: ignore

from helix_fhir_client_sdk.exceptions.fhir_sender_exception import FhirSenderException
from helix_fhir_client_sdk.loggers.fhir_logger import FhirLogger
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse
from helix_fhir_client_sdk.validators.fhir_validator import FhirValidator

logging.basicConfig(level=logging.DEBUG)


# stores the tuple in the cache
class WellKnownConfigurationCacheEntry(NamedTuple):
    auth_url: Optional[str]
    last_updated_utc: datetime


class FhirClient:
    """
    Class used to call FHIR server
    """

    _time_to_live_in_secs_for_cache: int = 10 * 60

    # caches results from calls to well known configuration
    #   key is host name of fhir server, value is  auth_server_url
    _well_known_configuration_cache: Dict[str, WellKnownConfigurationCacheEntry] = {}

    # used to lock access to above cache
    _lock: Lock = Lock()

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
        self._sort_fields: Optional[List[str]] = None
        self._auth_server_url: Optional[str] = None
        self._auth_scopes: Optional[List[str]] = None
        self._login_token: Optional[str] = None
        self._access_token: Optional[str] = None
        self._logger: Optional[FhirLogger] = None
        self._adapter: Optional[BaseAdapter] = None
        self._limit: Optional[int] = None
        self._validation_server_url: Optional[str] = None
        self._separate_bundle_resources: bool = (
            False  # for each entry in bundle create a property for each resource
        )

    def action(self, action: str) -> "FhirClient":
        """
        :param action: (Optional) do an action e.g., $everything
        """
        self._action = action
        return self

    def action_payload(self, action_payload: Dict[str, Any]) -> "FhirClient":
        """
        :param action_payload: (Optional) if action such as $graph needs a http payload
        """
        self._action_payload = action_payload
        return self

    def resource(self, resource: str) -> "FhirClient":
        """
        :param resource: what FHIR resource to retrieve
        """
        self._resource = resource
        return self

    def id_(self, id_: Union[List[str], str]) -> "FhirClient":
        self._id = id_
        return self

    def url(self, url: str) -> "FhirClient":
        """
        :param url: server to call for FHIR
        """
        self._url = url
        return self

    def validation_server_url(self, validation_server_url: str) -> "FhirClient":
        """
        :param validation_server_url: server to call for FHIR validation
        """
        self._validation_server_url = validation_server_url
        return self

    def additional_parameters(self, additional_parameters: List[str]) -> "FhirClient":
        """
        :param additional_parameters: Any additional parameters to send with request
        """
        self._additional_parameters = additional_parameters
        return self

    def filter_by_resource(self, filter_by_resource: str) -> "FhirClient":
        """
        :param filter_by_resource: filter the resource by this. e.g., /Condition?Patient=1
                (resource=Condition, filter_by_resource=Patient)
        """
        self._filter_by_resource = filter_by_resource
        return self

    def filter_parameter(self, filter_parameter: str) -> "FhirClient":
        """
        :param filter_parameter: Instead of requesting ?patient=1,
                do ?subject:Patient=1 (if filter_parameter is subject)
        """
        self._filter_parameter = filter_parameter
        return self

    def include_only_properties(
        self, include_only_properties: List[str]
    ) -> "FhirClient":
        """
        :param include_only_properties: includes only these properties
        """
        self._include_only_properties = include_only_properties
        return self

    def page_number(self, page_number: int) -> "FhirClient":
        """
        :param page_number: page number to load
        """
        self._page_number = page_number
        return self

    def page_size(self, page_size: int) -> "FhirClient":
        """
        :param page_size: (Optional) use paging and get this many items in each page
        """

        self._page_size = page_size
        return self

    def last_updated_after(self, last_updated_after: datetime) -> "FhirClient":
        """
        :param last_updated_after: (Optional) Only get records newer than this
        """
        self._last_updated_after = last_updated_after
        return self

    def last_updated_before(self, last_updated_before: datetime) -> "FhirClient":
        """
        :param last_updated_before: (Optional) Only get records older than this
        """
        self._last_updated_before = last_updated_before
        return self

    def sort_fields(self, sort_fields: List[str]) -> "FhirClient":
        """
        :param sort_fields: sort by fields in the resource
        """
        self._sort_fields = sort_fields
        return self

    def auth_server_url(self, auth_server_url: str) -> "FhirClient":
        """
        :param auth_server_url: server url to call to get the authentication token
        """
        self._auth_server_url = auth_server_url
        return self

    def auth_scopes(self, auth_scopes: List[str]) -> "FhirClient":
        """
        :param auth_scopes: list of scopes to request permission for e.g., system/AllergyIntolerance.read
        """
        self._auth_scopes = auth_scopes
        return self

    def login_token(self, login_token: str) -> "FhirClient":
        """
        :param login_token: login token to use
        """
        self._login_token = login_token
        return self

    def client_credentials(self, client_id: str, client_secret: str) -> "FhirClient":
        self._login_token = self._create_login_token(
            client_id=client_id, client_secret=client_secret
        )
        logging.info(f"Generated login token for client_id={client_id}")
        return self

    def logger(self, logger: FhirLogger) -> "FhirClient":
        self._logger = logger
        return self

    def adapter(self, adapter: BaseAdapter) -> "FhirClient":
        self._adapter = adapter
        return self

    def limit(self, limit: int) -> "FhirClient":
        self._limit = limit
        return self

    @property
    def access_token(self) -> Optional[str]:
        # if we have an auth server url but no access token then get an access token
        if self._login_token and not self._auth_server_url:
            http: Session = self._create_http_session()
            # try to get auth_server_url from well known configuration
            self._auth_server_url = (
                self._get_auth_server_url_from_well_known_configuration()
            )
            if self._auth_server_url:
                logging.info(
                    f"Received {self._auth_server_url} from well_known configuration of server: {self._url}"
                )
        if self._auth_server_url and not self._access_token:
            assert (
                self._login_token
            ), "login token must be present if auth_server_url is set"
            http = self._create_http_session()
            self._access_token = self.authenticate(
                http=http,
                auth_server_url=self._auth_server_url,
                auth_scopes=self._auth_scopes,
                login_token=self._login_token,
            )
        return self._access_token

    @access_token.setter
    def access_token(self, value: str) -> None:
        self._access_token = value

    def set_access_token(self, value: str) -> "FhirClient":
        self.access_token = value
        return self

    def delete(self) -> Response:
        if not self._id:
            raise ValueError("delete requires the ID of FHIR object to delete")
        if not self._resource:
            raise ValueError("delete requires a FHIR resource type")
        full_uri: furl = furl(self._url)
        full_uri /= self._resource
        full_uri /= self._id
        # setup retry
        http: Session = self._create_http_session()

        # set up headers
        headers: Dict[str, str] = {}

        # set access token in request if present
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        # actually make the request
        response: Response = http.delete(full_uri.tostr(), headers=headers)
        if response.ok:
            if self._logger:
                self._logger.info(f"Successfully deleted: {full_uri}")

        return response

    def separate_bundle_resources(
        self, separate_bundle_resources: bool
    ) -> "FhirClient":
        self._separate_bundle_resources = separate_bundle_resources
        return self

    def get(self) -> FhirGetResponse:
        assert self._url, "No FHIR server url was set"
        retries: int = 2
        while retries >= 0:
            retries = retries - 1
            # create url and query to request from FHIR server
            resources: str = ""
            full_uri: furl = furl(self._url)
            full_uri /= self._resource
            if self._id:
                if self._filter_by_resource:
                    if self._filter_parameter:
                        # ?subject:Patient=27384972
                        full_uri.args[
                            f"{self._filter_parameter}:{self._filter_by_resource}"
                        ] = self._id
                    else:
                        # ?patient=27384972
                        full_uri.args[self._filter_by_resource.lower()] = self._id
                elif isinstance(self._id, list):
                    if len(self._id) == 1:
                        full_uri /= self._id
                    else:
                        full_uri.args["id"] = ",".join(self._id)
                else:
                    full_uri /= self._id
            # add action to url
            if self._action:
                full_uri /= self._action
            # add a query for just desired properties
            if self._include_only_properties:
                full_uri.args["_elements"] = ",".join(self._include_only_properties)
            if self._page_size and self._page_number is not None:
                # noinspection SpellCheckingInspection
                full_uri.args["_count"] = self._page_size
                # noinspection SpellCheckingInspection
                full_uri.args["_getpagesoffset"] = self._page_number

            # add any sort fields
            if self._sort_fields is not None:
                full_uri.args["_sort"] = self._sort_fields

            # create full url by adding on any query parameters
            full_url: str = full_uri.url
            if self._additional_parameters:
                if len(full_uri.args) > 0:
                    full_url += "&"
                else:
                    full_url += "?"
                full_url += "&".join(self._additional_parameters)

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
            }

            # set access token in request if present
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"

            # actually make the request
            http: Session = self._create_http_session()
            response: Response = self._send_fhir_request(
                http, full_url, headers, payload
            )
            # if request is ok (200) then return the data
            if response.ok:
                if self._logger:
                    self._logger.info(f"Successfully retrieved: {full_url}")

                text = response.text
                if len(text) > 0:
                    response_json: Dict[str, Any] = json.loads(text)
                    # see if this is a Resource Bundle and un-bundle it
                    if (
                        "resourceType" in response_json
                        and response_json["resourceType"] == "Bundle"
                    ):
                        if "entry" in response_json:
                            entries: List[Dict[str, Any]] = response_json["entry"]
                            entry: Dict[str, Any]
                            resources_list: List[Dict[str, Any]] = []
                            for entry in entries:
                                if "resource" in entry:
                                    if self._separate_bundle_resources:
                                        if self._action != "$graph":
                                            raise Exception(
                                                "only $graph action with _separate_bundle_resources=True is supported at this moment"
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
                )
            elif response.status_code == 404:  # not found
                if self._logger:
                    self._logger.error(f"resource not found! {full_url}")
                return FhirGetResponse(
                    url=full_url,
                    responses=resources,
                    error=f"{response.status_code}",
                    access_token=self._access_token,
                )
            elif (
                response.status_code == 403 or response.status_code == 401
            ):  # forbidden or unauthorized
                if retries >= 0:
                    assert (
                        self._auth_server_url
                    ), f"{response.status_code} received from server but no auth_server_url was specified to use"
                    assert (
                        self._login_token
                    ), f"{response.status_code} received from server but no login_token was specified to use"
                    self._access_token = self.authenticate(
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
                        responses=resources,
                        error=f"{response.status_code}",
                        access_token=self._access_token,
                    )
            else:
                # some unexpected error
                if self._logger:
                    self._logger.error(
                        f"Fhir Receive failed [{response.status_code}]: {full_url} "
                    )
                error_text: str = response.text
                if self._logger:
                    self._logger.error(error_text)
                return FhirGetResponse(
                    url=full_url,
                    responses=resources,
                    access_token=self._access_token,
                    error=f"{response.status_code} {error_text}",
                )
        raise Exception("Could not talk to FHIR server after multiple tries")

    def _send_fhir_request(
        self,
        http: Session,
        full_url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
    ) -> Response:
        if self._action == "$graph":
            if self._logger:
                self._logger.info(f"sending a post: {full_url}")
            logging.info(f"sending a post: {full_url}")
            if payload:
                return http.post(full_url, headers=headers, json=payload)
            else:
                raise Exception(
                    "$graph needs a payload to define the returning response (use action_payload parameter)"
                )
        else:
            if self._logger:
                self._logger.info(f"sending a get: {full_url}")
            logging.info(f"sending a get: {full_url}")
            return http.get(full_url, headers=headers, data=payload)

    def _create_http_session(self) -> Session:
        retry_strategy = Retry(
            total=5,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=[
                "HEAD",
                "GET",
                "PUT",
                "DELETE",
                "OPTIONS",
                "TRACE",
                "POST",
            ],
            backoff_factor=5,
        )
        # create http session
        adapter = HTTPAdapter(max_retries=retry_strategy)
        http = requests.Session()
        http.mount("https://", adapter)
        http.mount("http://", adapter)
        if self._adapter:
            http.mount("http://", self._adapter)
        else:
            http.mount("http://", adapter)
        return http

    def get_in_batches(self) -> FhirGetResponse:
        # if paging is requested then iterate through the pages until the response is empty
        assert self._url
        assert self._page_size
        self._page_number = 0
        resources_list: List[str] = []
        while True:
            result: FhirGetResponse = self.get()
            if not result.error and bool(result.responses):
                resources_list.extend(json.loads(result.responses))
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
        )

    @staticmethod
    def _create_login_token(client_id: str, client_secret: str) -> str:
        """
        Creates a login token given client_id and client_secret
        :return: login token
        :rtype: str
        """
        token: str = base64.b64encode(
            f"{client_id}:{client_secret}".encode("ascii")
        ).decode("ascii")
        return token

    @staticmethod
    def authenticate(
        http: Session,
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
        :rtype: str
        """
        assert auth_server_url
        assert auth_scopes
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

        response: Response = http.request(
            "POST", auth_server_url, headers=headers, data=payload
        )

        # token = response.text.encode('utf8')
        token_text: str = response.text
        if not token_text:
            return None
        token_json: Dict[str, Any] = json.loads(token_text)

        if "access_token" not in token_json:
            raise Exception(f"No access token found in {token_json}")
        access_token: str = token_json["access_token"]
        return access_token

    def merge(self, json_data_list: List[str],) -> FhirMergeResponse:
        """
        Calls $merge function on FHIR server
        :param json_data_list:
        :type json_data_list:
        :return:
        :rtype:
        """
        assert self._url, "No FHIR server url was set"
        logging.info(f"Calling $merge on {self._url}")

        retries: int = 2
        while retries >= 0:
            retries = retries - 1
            full_uri: furl = furl(self._url)
            assert self._resource
            full_uri /= self._resource
            headers = {"Content-Type": "application/fhir+json"}
            responses: List[Dict[str, Any]] = []
            http: Session = self._create_http_session()
            # set access token in request if present
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"

            try:
                resource_json_list: List[Dict[str, Any]] = [
                    json.loads(json_data) for json_data in json_data_list
                ]
                if self._validation_server_url:
                    resource_json: Dict[str, Any]
                    for resource_json in resource_json_list:
                        FhirValidator.validate_fhir_resource(
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
                response: Optional[Response] = None
                try:
                    # should we check if it exists and do a POST then?
                    response = http.post(
                        url=resource_uri.url, data=json_payload_bytes, headers=headers
                    )
                    if response and response.ok:
                        # logging does not work in UDFs since they run on nodes
                        # if progress_logger:
                        #     progress_logger.write_to_log(
                        #         f"Posted to {resource_uri.url}: {json_data}"
                        #     )
                        # check if response is json
                        response_text = response.text
                        if response_text:
                            try:
                                responses = json.loads(response_text)
                            except ValueError as e:
                                responses = [{"issue": str(e)}]
                        else:
                            responses = []
                        # print(f"Posted to {resource_uri.url}: {json_payload}. responses={responses}")
                    elif (
                        response.status_code == 403 or response.status_code == 401
                    ):  # forbidden or unauthorized
                        if retries >= 0:
                            assert (
                                self._auth_server_url
                            ), f"{response.status_code} received from server but no auth_server_url was specified to use"
                            assert (
                                self._login_token
                            ), f"{response.status_code} received from server but no login_token was specified to use"
                            self._access_token = self.authenticate(
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
                        logging.info(
                            f"response for {full_uri.tostr()}: {response.status_code}"
                        )
                        response.raise_for_status()
                except requests.exceptions.HTTPError as e:
                    raise FhirSenderException(
                        url=resource_uri.url,
                        json_data=json_payload,
                        response_text=response.text if response else "",
                        response_status_code=response.status_code if response else None,
                        exception=e,
                        message=f"HttpError: {e}",
                    ) from e
                except Exception as e:
                    raise FhirSenderException(
                        url=resource_uri.url,
                        json_data=json_payload,
                        response_text=response.text if response else "",
                        response_status_code=response.status_code if response else None,
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

    def _get_auth_server_url_from_well_known_configuration(self) -> Optional[str]:
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
                logging.info(
                    f"Returning auth_url from cache for {host_name}: {cached_endpoint}"
                )
                return cached_endpoint
        full_uri /= ".well-known/smart-configuration"
        logging.info(f"Calling {full_uri.tostr()}")
        http = self._create_http_session()
        response: Response = http.get(full_uri.tostr())
        if response and response.ok and response.text:
            content: Dict[str, Any] = json.loads(response.text)
            token_endpoint: Optional[str] = str(content["token_endpoint"])
            with self._lock:
                self._well_known_configuration_cache[
                    host_name
                ] = WellKnownConfigurationCacheEntry(
                    auth_url=token_endpoint, last_updated_utc=datetime.utcnow()
                )
            return token_endpoint
        else:
            with self._lock:
                self._well_known_configuration_cache[
                    host_name
                ] = WellKnownConfigurationCacheEntry(
                    auth_url=None, last_updated_utc=datetime.utcnow()
                )
            return None
