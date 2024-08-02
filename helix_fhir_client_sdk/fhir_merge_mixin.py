import asyncio
import json
import time
from typing import Optional, List, Dict, Any, Union, cast

import requests
from aiohttp import ClientResponse, ClientSession
from furl import furl
from urllib import parse

from helix_fhir_client_sdk.dictionary_writer import convert_dict_to_str
from helix_fhir_client_sdk.exceptions.fhir_sender_exception import FhirSenderException
from helix_fhir_client_sdk.exceptions.fhir_validation_exception import (
    FhirValidationException,
)
from helix_fhir_client_sdk.responses.fhir_client_protocol import FhirClientProtocol
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse
from helix_fhir_client_sdk.responses.fhir_response_processor import (
    FhirResponseProcessor,
)
from helix_fhir_client_sdk.utilities.fhir_client_logger import FhirClientLogger
from helix_fhir_client_sdk.validators.async_fhir_validator import AsyncFhirValidator


class FhirMergeMixin(FhirClientProtocol):
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
        instance_variables_text = convert_dict_to_str(
            FhirClientLogger.get_variables_to_log(vars(self))
        )
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
            headers.update(self._additional_request_headers)
            self._internal_logger.debug(f"Request headers: {headers}")

            responses: List[Dict[str, Any]] = []
            start_time: float = time.time()
            async with self.create_http_session() as http:
                # set access token in request if present
                if await self.get_access_token_async():
                    headers["Authorization"] = (
                        f"Bearer {await self.get_access_token_async()}"
                    )

                try:
                    resource_json_list_incoming: List[Dict[str, Any]] = [
                        json.loads(json_data) for json_data in json_data_list
                    ]
                    resource_json_list_clean: List[Dict[str, Any]]
                    errors: List[Dict[str, Any]] = []
                    if self._validation_server_url:
                        resource_json_list_clean = await self.validate_content(
                            errors=errors,
                            http=http,
                            resource_json_list_incoming=resource_json_list_incoming,
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
                                    self._access_token = (
                                        await self._refresh_token_function(
                                            auth_server_url=self._auth_server_url,
                                            auth_scopes=self._auth_scopes,
                                            login_token=self._login_token,
                                        )
                                    )
                                    if self._access_token:
                                        # try again
                                        continue
                                else:
                                    # out of retries so just fail now
                                    response.raise_for_status()
                            else:  # other HTTP errors
                                self._internal_logger.info(
                                    f"POST response for {resource_uri.url}: {response.status}"
                                )
                                response_text = await FhirResponseProcessor.get_safe_response_text_async(
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
                                    error=(
                                        json.dumps(response_text)
                                        if response_text
                                        else None
                                    ),
                                    access_token=self._access_token,
                                    status=response.status if response.status else 500,
                                )
                        except requests.exceptions.HTTPError as e:
                            raise FhirSenderException(
                                request_id=request_id,
                                url=resource_uri.url,
                                headers=headers,
                                json_data=json_payload,
                                response_text=await FhirResponseProcessor.get_safe_response_text_async(
                                    response=response
                                ),
                                response_status_code=(
                                    response.status if response else None
                                ),
                                exception=e,
                                variables=FhirClientLogger.get_variables_to_log(
                                    vars(self)
                                ),
                                message=f"HttpError: {e}",
                                elapsed_time=time.time() - start_time,
                            ) from e
                        except Exception as e:
                            raise FhirSenderException(
                                request_id=request_id,
                                url=resource_uri.url,
                                headers=headers,
                                json_data=json_payload,
                                response_text=await FhirResponseProcessor.get_safe_response_text_async(
                                    response=response
                                ),
                                response_status_code=(
                                    response.status if response else None
                                ),
                                exception=e,
                                variables=FhirClientLogger.get_variables_to_log(
                                    vars(self)
                                ),
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
                                + f"variables={convert_dict_to_str(FhirClientLogger.get_variables_to_log(vars(self)))}"
                            )
                        )

                return FhirMergeResponse(
                    request_id=request_id,
                    url=resource_uri.url,
                    responses=responses + errors,
                    error=(
                        json.dumps(responses + errors)
                        if response_status != 200
                        else None
                    ),
                    access_token=self._access_token,
                    status=response_status if response_status else 500,
                    json_data=json_payload,
                )

        raise Exception(
            f"Could not talk to FHIR server after multiple tries: {request_id}"
        )

    async def validate_content(
        self,
        *,
        errors: List[Dict[str, Any]],
        http: ClientSession,
        resource_json_list_incoming: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        resource_json_list_clean: List[Dict[str, Any]] = []
        assert self._validation_server_url
        # if there is only resource then just validate that individually
        if len(resource_json_list_incoming) == 1:
            resource_json: Dict[str, Any] = resource_json_list_incoming[0]
            try:
                await AsyncFhirValidator.validate_fhir_resource(
                    http=http,
                    json_data=json.dumps(resource_json),
                    resource_name=cast(Optional[str], resource_json.get("resourceType"))
                    or self._resource
                    or "",
                    validation_server_url=self._validation_server_url,
                    access_token=await self.get_access_token_async(),
                )
                resource_json_list_clean.append(resource_json)
            except FhirValidationException as e:
                errors.append(
                    {
                        "id": (
                            resource_json.get("id") if resource_json.get("id") else None
                        ),
                        "resourceType": resource_json.get("resourceType"),
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
                        or self._resource
                        or "",
                        validation_server_url=self._validation_server_url,
                        access_token=await self.get_access_token_async(),
                    )
                    resource_json_list_clean.append(resource_json)
                except FhirValidationException as e:
                    errors.append(
                        {
                            "id": resource_json.get("id"),
                            "resourceType": resource_json.get("resourceType"),
                            "issue": e.issue,
                        }
                    )
        return resource_json_list_clean

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
