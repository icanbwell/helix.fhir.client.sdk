from __future__ import annotations

import base64
import json
from datetime import datetime
from threading import Lock
from typing import Optional, List, Dict, Any, TYPE_CHECKING, cast

from aiohttp import ClientResponse, ClientSession
from furl import furl

from helix_fhir_client_sdk.function_types import RefreshTokenFunction
from helix_fhir_client_sdk.responses.fhir_client_protocol import FhirClientProtocol
from helix_fhir_client_sdk.well_known_configuration import (
    WellKnownConfigurationCacheEntry,
)

if TYPE_CHECKING:
    from helix_fhir_client_sdk.fhir_client import FhirClient


class FhirAuthMixin(FhirClientProtocol):
    _time_to_live_in_secs_for_cache: int = 10 * 60

    # caches result from calls to well known configuration
    #   key is host name of fhir server, value is  auth_server_url
    _well_known_configuration_cache: Dict[str, WellKnownConfigurationCacheEntry] = {}

    # used to lock access to above cache
    _well_known_configuration_cache_lock: Lock = Lock()

    def __init__(self) -> None:
        self._auth_server_url: Optional[str] = None
        self._auth_wellknown_url: Optional[str] = None
        self._auth_scopes: Optional[List[str]] = None
        self._login_token: Optional[str] = None
        self._client_id: Optional[str] = None
        self._access_token: Optional[str] = None

    def auth_server_url(self, auth_server_url: str | None) -> "FhirClient":
        """
        auth server url


        :param auth_server_url: server url to call to get the authentication token
        """
        self._auth_server_url = auth_server_url
        return cast("FhirClient", self)

    def auth_wellknown_url(self, auth_wellknown_url: str) -> "FhirClient":
        """
        Specify the well known configuration url to get the auth server url

        :param auth_wellknown_url: well known configuration url
        """
        self._auth_wellknown_url = auth_wellknown_url
        return cast("FhirClient", self)

    def auth_scopes(self, auth_scopes: List[str]) -> "FhirClient":
        """
        auth scopes


        :param auth_scopes: list of scopes to request permission for e.g., system/AllergyIntolerance.read
        """
        assert isinstance(auth_scopes, list), f"{type(auth_scopes)} is not a list"
        self._auth_scopes = auth_scopes
        return cast("FhirClient", self)

    def login_token(self, login_token: str) -> "FhirClient":
        """
        login token


        :param login_token: login token to use
        """
        self._login_token = login_token
        return cast("FhirClient", self)

    async def get_access_token_async(self) -> Optional[str]:
        """
        Gets current access token


        :return: access token if any
        """
        if self._access_token:
            return self._access_token
        # if we have an auth server url but no access token then get access token
        if self._login_token and not self._auth_server_url:
            # try to get auth_server_url from well known configuration
            self.auth_server_url(
                await self._get_auth_server_url_from_well_known_configuration_async()
            )
            if self._auth_server_url and self._logger:
                self._logger.info(
                    f"Received {self._auth_server_url} from well_known configuration of server: {self._url}"
                )
        self.set_access_token(
            await self._refresh_token_function(
                auth_server_url=self._auth_server_url,
                auth_scopes=self._auth_scopes,
                login_token=self._login_token,
            )
        )
        return self._access_token

    def authenticate_async_wrapper(self) -> RefreshTokenFunction:
        """
        Returns a function that authenticates with auth server


        :return: refresh token function
        """

        async def refresh_token(
            auth_server_url: Optional[str],
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

    async def _get_auth_server_url_from_well_known_configuration_async(
        self,
    ) -> Optional[str]:
        """
        Finds the auth server url via the well known configuration if it exists


        :return: auth server url or None
        """
        if self._auth_wellknown_url:
            host_name: str = furl(self._auth_wellknown_url).host
            if host_name in self._well_known_configuration_cache:
                entry: Optional[WellKnownConfigurationCacheEntry] = (
                    self._well_known_configuration_cache.get(host_name)
                )
                if entry and (
                    (datetime.utcnow() - entry.last_updated_utc).seconds
                    < self._time_to_live_in_secs_for_cache
                ):
                    cached_endpoint: Optional[str] = entry.auth_url
                    # self._internal_logger.info(
                    #     f"Returning auth_url from cache for {host_name}: {cached_endpoint}"
                    # )
                    return cached_endpoint
            async with self.create_http_session() as http:
                try:
                    response: ClientResponse = await http.get(self._auth_wellknown_url)
                    text_ = await response.text()
                    if response and response.status == 200 and text_:
                        content: Dict[str, Any] = json.loads(text_)
                        token_endpoint: Optional[str] = str(content["token_endpoint"])
                        with self._well_known_configuration_cache_lock:
                            self._well_known_configuration_cache[host_name] = (
                                WellKnownConfigurationCacheEntry(
                                    auth_url=token_endpoint,
                                    last_updated_utc=datetime.utcnow(),
                                )
                            )
                        return token_endpoint
                    else:
                        with self._well_known_configuration_cache_lock:
                            self._well_known_configuration_cache[host_name] = (
                                WellKnownConfigurationCacheEntry(
                                    auth_url=None, last_updated_utc=datetime.utcnow()
                                )
                            )
                        return None
                except Exception as e:
                    raise Exception(
                        f"Error getting well known configuration from {self._auth_wellknown_url}"
                    ) from e
        else:
            full_uri: furl = furl(furl(self._url).origin)
            host_name = full_uri.tostr()
            if host_name in self._well_known_configuration_cache:
                entry = self._well_known_configuration_cache.get(host_name)
                if entry and (
                    (datetime.utcnow() - entry.last_updated_utc).seconds
                    < self._time_to_live_in_secs_for_cache
                ):
                    cached_endpoint = entry.auth_url
                    # self._internal_logger.info(
                    #     f"Returning auth_url from cache for {host_name}: {cached_endpoint}"
                    # )
                    return cached_endpoint
            full_uri /= ".well-known/smart-configuration"
            self._internal_logger.info(f"Calling {full_uri.tostr()}")
            async with self.create_http_session() as http:
                try:
                    response = await http.get(full_uri.tostr())
                    text_ = await response.text()
                    if response and response.status == 200 and text_:
                        content = json.loads(text_)
                        token_endpoint = str(content["token_endpoint"])
                        with self._well_known_configuration_cache_lock:
                            self._well_known_configuration_cache[host_name] = (
                                WellKnownConfigurationCacheEntry(
                                    auth_url=token_endpoint,
                                    last_updated_utc=datetime.utcnow(),
                                )
                            )
                        return token_endpoint
                    else:
                        with self._well_known_configuration_cache_lock:
                            self._well_known_configuration_cache[host_name] = (
                                WellKnownConfigurationCacheEntry(
                                    auth_url=None, last_updated_utc=datetime.utcnow()
                                )
                            )
                        return None
                except Exception as e:
                    raise Exception(
                        f"Error getting well known configuration from {full_uri.tostr()}"
                    ) from e

    @staticmethod
    async def authenticate_async(
        *,
        session: ClientSession,
        auth_server_url: Optional[str],
        auth_scopes: Optional[List[str]],
        login_token: Optional[str],
    ) -> Optional[str]:
        if not auth_server_url or not login_token:
            return None
        assert auth_server_url, "No auth server url was set"
        assert login_token, "No login token was set"
        payload: str = (
            "grant_type=client_credentials&scope=" + "%20".join(auth_scopes)
            if auth_scopes
            else "grant_type=client_credentials"
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
        if self._logger:
            self._logger.info(f"Generated login token for client_id={client_id}")
        return cast("FhirClient", self)
