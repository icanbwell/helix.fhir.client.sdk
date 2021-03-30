import json
from datetime import datetime
from typing import Dict, Optional, List, Union, Any
from furl import furl
from urllib3 import Retry  # type: ignore
from requests.adapters import HTTPAdapter, BaseAdapter
import requests
from requests import Response, Session
import base64

from helix_fhir_client_sdk.fhir_logger import FhirLogger
from helix_fhir_client_sdk.fhir_request_response import FhirRequestResponse


class FhirClient:
    def __init__(self) -> None:
        self._action: Optional[str] = None
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

    def action(self, action: str) -> "FhirClient":
        """
        :param action: (Optional) do an action e.g., $everything
        """
        self._action = action
        return self

    def resource(self, resource: str) -> "FhirClient":
        """
        :param resource: what FHIR resource to retrieve
        """
        self._resource = resource
        return self

    def id_(self, id_: Optional[Union[List[str], str]]) -> "FhirClient":
        self._id = id_
        return self

    def url(self, url: str) -> "FhirClient":
        """
        :param url: server to call for FHIR
        """
        self._url = url
        return self

    def additional_parameters(
        self, additional_parameters: Optional[List[str]]
    ) -> "FhirClient":
        """
        :param additional_parameters: Any additional parameters to send with request
        """
        self._additional_parameters = additional_parameters
        return self

    def filter_by_resource(self, filter_by_resource: Optional[str]) -> "FhirClient":
        """
        :param filter_by_resource: filter the resource by this. e.g., /Condition?Patient=1
                (resource=Condition, filter_by_resource=Patient)
        """
        self._filter_by_resource = filter_by_resource
        return self

    def filter_parameter(self, filter_parameter: Optional[str]) -> "FhirClient":
        """
        :param filter_parameter: Instead of requesting ?patient=1,
                do ?subject:Patient=1 (if filter_parameter is subject)
        """
        self._filter_parameter = filter_parameter
        return self

    def include_only_properties(
        self, include_only_properties: Optional[List[str]]
    ) -> "FhirClient":
        """
        :param include_only_properties: includes only these properties
        """
        self._include_only_properties = include_only_properties
        return self

    def page_number(self, page_number: Optional[int]) -> "FhirClient":
        """
        :param page_number: page number to load
        """
        self._page_number = page_number
        return self

    def page_size(self, page_size: Optional[int]) -> "FhirClient":
        """
        :param page_size: (Optional) use paging and get this many items in each page
        """

        self._page_size = page_size
        return self

    def last_updated_after(
        self, last_updated_after: Optional[datetime]
    ) -> "FhirClient":
        """
        :param last_updated_after: (Optional) Only get records newer than this
        """
        self._last_updated_after = last_updated_after
        return self

    def last_updated_before(
        self, last_updated_before: Optional[datetime]
    ) -> "FhirClient":
        """
        :param last_updated_before: (Optional) Only get records older than this
        """
        self._last_updated_before = last_updated_before
        return self

    def sort_fields(self, sort_fields: Optional[List[str]]) -> "FhirClient":
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

    def auth_scopes(self, auth_scopes: Optional[List[str]]) -> "FhirClient":
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
        self._login_token = self.create_login_token(
            client_id=client_id, client_secret=client_secret
        )
        return self

    def logger(self, logger: FhirLogger) -> "FhirClient":
        self._logger = logger
        return self

    def adapter(self, adapter: BaseAdapter) -> "FhirClient":
        self._adapter = adapter
        return self

    def send_request(self) -> FhirRequestResponse:
        retries: int = 2
        while retries >= 0:
            retries = retries - 1
            # create url and query to request from FHIR server
            resources: List[str] = []
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

            # setup retry
            retry_strategy = Retry(
                total=5,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=[
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

            # set up headers
            payload: Dict[str, str] = {}
            headers = {"Accept": "application/fhir+json,application/json+fhir"}

            # if we have an auth server url but no access token then get an access token
            if self._auth_server_url and not self._access_token:
                assert (
                    self._login_token
                ), "login token must be present if auth_server_url is set"
                self._access_token = self.authenticate(
                    http=http,
                    auth_server_url=self._auth_server_url,
                    auth_scopes=self._auth_scopes,
                    login_token=self._login_token,
                )
            # set access token in request if present
            if self._access_token:
                headers["Authorization"] = f"Bearer {self._access_token}"

            # actually make the request
            response: Response = http.get(full_url, headers=headers, data=payload)
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
                        # resources.append(text)
                        if "entry" in response_json:
                            # iterate through the entry list
                            # have to split these here otherwise when Spark loads them it can't handle
                            # that items in the entry array can have different types
                            entries: List[Dict[str, Any]] = response_json["entry"]
                            entry: Dict[str, Any]
                            for entry in entries:
                                if "resource" in entry:
                                    resources.append(json.dumps(entry["resource"]))
                    else:
                        resources.append(text)
                return FhirRequestResponse(
                    url=full_url, responses=resources, error=None
                )
            elif response.status_code == 404:  # not found
                if self._logger:
                    self._logger.error(f"resource not found! GET {full_uri}")
                return FhirRequestResponse(
                    url=full_url, responses=resources, error=f"{response.status_code}"
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
                    return FhirRequestResponse(
                        url=full_url,
                        responses=resources,
                        error=f"{response.status_code}",
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
                return FhirRequestResponse(
                    url=full_url,
                    responses=[],
                    error=f"{response.status_code} {error_text}",
                )
        raise Exception("Could not talk to FHIR server after multiple tries")

    @staticmethod
    def create_login_token(client_id: str, client_secret: str) -> str:
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

        access_token: str = token_json["access_token"]
        return access_token
