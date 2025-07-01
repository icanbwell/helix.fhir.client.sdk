import json
import time
from collections.abc import AsyncGenerator, Generator
from typing import (
    Any,
    cast,
)

import requests
from furl import furl

from helix_fhir_client_sdk.dictionary_writer import convert_dict_to_str
from helix_fhir_client_sdk.exceptions.fhir_sender_exception import FhirSenderException
from helix_fhir_client_sdk.exceptions.fhir_validation_exception import (
    FhirValidationException,
)
from helix_fhir_client_sdk.responses.fhir_client_protocol import FhirClientProtocol
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse
from helix_fhir_client_sdk.structures.get_access_token_result import (
    GetAccessTokenResult,
)
from helix_fhir_client_sdk.utilities.async_runner import AsyncRunner
from helix_fhir_client_sdk.utilities.fhir_client_logger import FhirClientLogger
from helix_fhir_client_sdk.utilities.list_chunker import ListChunker
from helix_fhir_client_sdk.utilities.retryable_aiohttp_client import (
    RetryableAioHttpClient,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_response import (
    RetryableAioHttpResponse,
)
from helix_fhir_client_sdk.validators.async_fhir_validator import AsyncFhirValidator


class FhirMergeMixin(FhirClientProtocol):
    async def validate_content(
        self,
        *,
        errors: list[dict[str, Any]],
        resource_json_list_incoming: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        resource_json_list_clean: list[dict[str, Any]] = []
        assert self._validation_server_url
        # if there is only resource then just validate that individually
        if len(resource_json_list_incoming) == 1:
            resource_json: dict[str, Any] = resource_json_list_incoming[0]
            try:
                access_token_result: GetAccessTokenResult = await self.get_access_token_async()
                access_token: str | None = access_token_result.access_token

                await AsyncFhirValidator.validate_fhir_resource(
                    fn_get_session=lambda: self.create_http_session(),
                    json_data=json.dumps(resource_json),
                    resource_name=cast(str | None, resource_json.get("resourceType")) or self._resource or "",
                    validation_server_url=self._validation_server_url,
                    access_token=access_token,
                )
                resource_json_list_clean.append(resource_json)
            except FhirValidationException as e:
                errors.append(
                    {
                        "id": (resource_json.get("id") if resource_json.get("id") else None),
                        "resourceType": resource_json.get("resourceType"),
                        "issue": e.issue,
                    }
                )
        else:
            for resource_json in resource_json_list_incoming:
                try:
                    access_token_result1: GetAccessTokenResult = await self.get_access_token_async()
                    access_token1: str | None = access_token_result1.access_token
                    await AsyncFhirValidator.validate_fhir_resource(
                        fn_get_session=lambda: self.create_http_session(),
                        json_data=json.dumps(resource_json),
                        resource_name=resource_json.get("resourceType") or self._resource or "",
                        validation_server_url=self._validation_server_url,
                        access_token=access_token1,
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

    async def merge_async(
        self,
        *,
        id_: str | None = None,
        json_data_list: list[str],
        batch_size: int | None = None,
    ) -> AsyncGenerator[FhirMergeResponse, None]:
        """
        Calls $merge function on FHIR server


        :param json_data_list: list of resources to send
        :param id_: id of the resource to merge
        :param batch_size: size of each batch
        :return: response
        """
        assert self._url, "No FHIR server url was set"
        assert isinstance(json_data_list, list), "This function requires a list"

        self._internal_logger.debug(
            f"Calling $merge on {self._url} with client_id={self._client_id} and scopes={self._auth_scopes}"
        )
        instance_variables_text = convert_dict_to_str(FhirClientLogger.get_variables_to_log(vars(self)))
        if self._internal_logger:
            self._internal_logger.info(f"parameters: {instance_variables_text}")
        else:
            self._internal_logger.info(f"LOGLEVEL (InternalLogger): {self._log_level}")
            self._internal_logger.info(f"parameters: {instance_variables_text}")

        request_id: str | None = None
        response_status: int | None = None
        full_uri: furl = furl(self._url)
        assert self._resource
        full_uri /= self._resource
        headers = {"Content-Type": "application/fhir+json"}
        headers.update(self._additional_request_headers)
        self._internal_logger.debug(f"Request headers: {headers}")

        responses: list[dict[str, Any]] = []
        start_time: float = time.time()
        # set access token in request if present
        access_token_result: GetAccessTokenResult = await self.get_access_token_async()
        access_token: str | None = access_token_result.access_token
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        try:
            resource_json_list_incoming: list[dict[str, Any]] = [json.loads(json_data) for json_data in json_data_list]
            resource_json_list_clean: list[dict[str, Any]]
            errors: list[dict[str, Any]] = []
            if self._validation_server_url:
                resource_json_list_clean = await self.validate_content(
                    errors=errors,
                    resource_json_list_incoming=resource_json_list_incoming,
                )
            else:
                resource_json_list_clean = resource_json_list_incoming

            if len(resource_json_list_clean) > 0:
                chunks: Generator[list[dict[str, Any]], None, None] = ListChunker.divide_into_chunks(
                    resource_json_list_clean, chunk_size=batch_size
                )
                chunk: list[dict[str, Any]]
                for chunk in chunks:
                    resource_uri: furl = full_uri.copy()
                    # if there is only item in the list then send it instead of having it in a list
                    json_payload: str = json.dumps(chunk[0]) if len(chunk) == 1 else json.dumps(chunk)
                    # json_payload_bytes: str = json_payload
                    obj_id = id_ or 1  # TODO: remove this once the node fhir accepts merge without a parameter
                    assert obj_id

                    if obj_id is not None and str(obj_id).strip():
                        resource_uri.path.segments.append(str(obj_id))
                    # Always append $merge
                    resource_uri.path.segments.append("$merge")

                    # Conditionally add the query parameter
                    if self._smart_merge is False:
                        resource_uri.add({"smartMerge": "false"})

                    response_text: str | None = None
                    try:
                        async with RetryableAioHttpClient(
                            fn_get_session=lambda: self.create_http_session(),
                            refresh_token_func=self._refresh_token_function,
                            tracer_request_func=self._trace_request_function,
                            retries=self._retry_count,
                            exclude_status_codes_from_retry=self._exclude_status_codes_from_retry,
                            use_data_streaming=self._use_data_streaming,
                            send_data_as_chunked=self._send_data_as_chunked,
                            compress=self._compress,
                            throw_exception_on_error=self._throw_exception_on_error,
                            log_all_url_results=self._log_all_response_urls,
                            access_token=self._access_token,
                            access_token_expiry_date=self._access_token_expiry_date,
                        ) as client:
                            # should we check if it exists and do a POST then?
                            response: RetryableAioHttpResponse = await client.post(
                                url=resource_uri.url,
                                data=json_payload,
                                headers=headers,
                            )
                            response_status = response.status
                            request_id = response.response_headers.get("X-Request-ID", None)
                            self._internal_logger.info(f"X-Request-ID={request_id}")
                            if response and response.status == 200:
                                response_text = await response.get_text_async()
                                if response_text:
                                    try:
                                        raw_response: list[dict[str, Any]] | dict[str, Any] = json.loads(response_text)
                                        if isinstance(raw_response, list):
                                            responses = raw_response
                                        else:
                                            responses = [raw_response]
                                    except ValueError as e:
                                        responses = [{"issue": str(e)}]
                                else:
                                    responses = []
                                yield FhirMergeResponse(
                                    request_id=request_id,
                                    url=resource_uri.url,
                                    responses=responses + errors,
                                    error=(json.dumps(responses + errors) if response_status != 200 else None),
                                    access_token=self._access_token,
                                    status=response_status if response_status else 500,
                                    json_data=json_payload,
                                )
                            else:  # other HTTP errors
                                self._internal_logger.info(f"POST response for {resource_uri.url}: {response.status}")
                                response_text = await response.get_text_async()
                                yield FhirMergeResponse(
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
                                    error=(json.dumps(response_text) if response_text else None),
                                    access_token=self._access_token,
                                    status=response.status if response.status else 500,
                                )
                    except requests.exceptions.HTTPError as e:
                        raise FhirSenderException(
                            request_id=request_id,
                            url=resource_uri.url,
                            headers=headers,
                            json_data=json_payload,
                            response_text=response_text,
                            response_status_code=response_status,
                            exception=e,
                            variables=FhirClientLogger.get_variables_to_log(vars(self)),
                            message=f"HttpError: {e}",
                            elapsed_time=time.time() - start_time,
                        ) from e
                    except Exception as e:
                        raise FhirSenderException(
                            request_id=request_id,
                            url=resource_uri.url,
                            headers=headers,
                            json_data=json_payload,
                            response_text=response_text,
                            response_status_code=response_status,
                            exception=e,
                            variables=FhirClientLogger.get_variables_to_log(vars(self)),
                            message=f"Unknown Error: {e}",
                            elapsed_time=time.time() - start_time,
                        ) from e
            else:
                json_payload = json.dumps(json_data_list)
                yield FhirMergeResponse(
                    request_id=request_id,
                    url=full_uri.url,
                    responses=responses + errors,
                    error=(json.dumps(responses + errors) if response_status != 200 else None),
                    access_token=self._access_token,
                    status=response_status if response_status else 500,
                    json_data=json_payload,
                )
        except AssertionError as e:
            if self._logger:
                self._logger.error(
                    Exception(
                        f"Assertion: FHIR send failed: {str(e)} for resource: {json_data_list}. "
                        + f"variables={convert_dict_to_str(FhirClientLogger.get_variables_to_log(vars(self)))}"
                    )
                )
            raise e

    def merge(
        self,
        *,
        id_: str | None = None,
        json_data_list: list[str],
        batch_size: int | None = None,
    ) -> FhirMergeResponse | None:
        """
        Calls $merge function on FHIR server


        :param json_data_list: list of resources to send
        :param batch_size: size of each batch
        :param id_: id of the resource to merge
        :return: response
        """

        result: FhirMergeResponse | None = AsyncRunner.run(
            FhirMergeResponse.from_async_generator(
                self.merge_async(id_=id_, json_data_list=json_data_list, batch_size=batch_size)
            )
        )
        return result
