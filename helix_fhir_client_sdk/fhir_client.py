import json
from datetime import datetime
from typing import Dict, Optional, List, Union, Any
from furl import furl
from urllib3 import Retry  # type: ignore
from requests.adapters import HTTPAdapter
import requests
from requests import Response

from helix_fhir_client_sdk.fhir_logger import FhirLogger
from helix_fhir_client_sdk.fhir_request_response import FhirRequestResponse


class FhirClient:
    @staticmethod
    def send_request(
        logger: FhirLogger,
        action: Optional[str],
        additional_parameters: Optional[List[str]],
        filter_by_resource: Optional[str],
        filter_parameter: Optional[str],
        resource_name: str,
        resource_id: Optional[Union[List[str], str]],
        server_url: str,
        token: Optional[str],
        include_only_properties: Optional[List[str]],
        page_number: Optional[int] = None,
        page_size: Optional[int] = None,
        last_updated_after: Optional[datetime] = None,
        last_updated_before: Optional[datetime] = None,
        sort_fields: Optional[List[str]] = None,
    ) -> FhirRequestResponse:
        resources: List[str] = []
        full_uri: furl = furl(server_url)
        full_uri /= resource_name
        if resource_id:
            if filter_by_resource:
                if filter_parameter:
                    # ?subject:Patient=27384972
                    full_uri.args[
                        f"{filter_parameter}:{filter_by_resource}"
                    ] = resource_id
                else:
                    # ?patient=27384972
                    full_uri.args[filter_by_resource.lower()] = resource_id
            elif isinstance(resource_id, list):
                if len(resource_id) == 1:
                    full_uri /= resource_id
                else:
                    full_uri.args["id"] = ",".join(resource_id)
            else:
                full_uri /= resource_id
        # add action to url
        if action:
            full_uri /= action
        # add a query for just desired properties
        if include_only_properties:
            full_uri.args["_elements"] = ",".join(include_only_properties)
        if page_size and page_number is not None:
            # noinspection SpellCheckingInspection
            full_uri.args["_count"] = page_size
            # noinspection SpellCheckingInspection
            full_uri.args["_getpagesoffset"] = page_number

        if sort_fields is not None:
            full_uri.args["_sort"] = sort_fields

        # create full url by adding on any query parameters
        full_url: str = full_uri.url
        if additional_parameters:
            if len(full_uri.args) > 0:
                full_url += "&"
            else:
                full_url += "?"
            full_url += "&".join(additional_parameters)

        # have to done here since this arg can be used twice
        if last_updated_before:
            if len(full_uri.args) > 0:
                full_url += "&"
            else:
                full_url += "?"
            full_url += (
                f"_lastUpdated=lt{last_updated_before.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            )
        if last_updated_after:
            if len(full_uri.args) > 0:
                full_url += "&"
            else:
                full_url += "?"
            full_url += (
                f"_lastUpdated=ge{last_updated_after.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            )

        payload: Dict[str, str] = {}
        headers = {"Accept": "application/fhir+json,application/json+fhir"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # print(f"Calling: {full_url}")
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
        adapter = HTTPAdapter(max_retries=retry_strategy)
        http = requests.Session()
        http.mount("https://", adapter)
        http.mount("http://", adapter)

        response: Response = http.get(full_url, headers=headers, data=payload)
        if response.ok:
            logger.info(f"Successfully retrieved: {full_url}")

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
        elif response.status_code == 404:
            logger.error(f"resource not found! GET {full_uri}")
            return FhirRequestResponse(
                url=full_url, responses=resources, error=f"{response.status_code}"
            )
        elif response.status_code == 403:
            # TODO: call get_auth_token() again to get a fresh token
            pass
        else:
            logger.error(f"Fhir Receive failed [{response.status_code}]: {full_url} ")
            error_text: str = response.text
            logger.error(error_text)
            return FhirRequestResponse(
                url=full_url,
                responses=[],
                error=f"{response.status_code} {error_text}",
            )
            # raise Exception(error_text) # swallow the error and continue processing
        return FhirRequestResponse(url=full_url, responses=resources, error=None)

    @staticmethod
    def get_auth_token(auth_server_url: str, auth_scopes: Optional[List[str]]) -> str:
        assert auth_server_url
        payload: str = (
            "grant_type=client_credentials&scope=" + "%20".join(auth_scopes)
            if auth_scopes
            else ""
        )
        # noinspection SpellCheckingInspection
        headers: Dict[str, str] = {
            "Accept": "application/json",
            "Authorization": "Basic "
            "YTBjZTc5NWQtYjQ0NC00NzkwLTlhMmMtNDllY2RjZWM2NGZlOkpoa"
            "VdpUllCajlDZU5VVG1sUnQxaUJhOEM4czVvejZy",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        response: Response = requests.request(
            "POST", auth_server_url, headers=headers, data=payload
        )

        # token = response.text.encode('utf8')
        token_text: str = response.text
        token_json: Dict[str, Any] = json.loads(token_text)

        token: str = token_json["access_token"]
        return token
