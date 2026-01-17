import json
import time
from collections import deque
from collections.abc import AsyncGenerator
from typing import Any, cast
from urllib import parse

import requests
from compressedfhir.fhir.fhir_bundle import FhirBundle
from compressedfhir.fhir.fhir_resource import FhirResource
from compressedfhir.fhir.fhir_resource_list import FhirResourceList
from furl import furl

from helix_fhir_client_sdk.dictionary_writer import convert_dict_to_str
from helix_fhir_client_sdk.exceptions.fhir_sender_exception import FhirSenderException
from helix_fhir_client_sdk.exceptions.fhir_validation_exception import (
    FhirValidationException,
)
from helix_fhir_client_sdk.responses.fhir_client_protocol import FhirClientProtocol
from helix_fhir_client_sdk.responses.merge.base_fhir_merge_resource_response_entry import (
    BaseFhirMergeResourceResponseEntry,
)
from helix_fhir_client_sdk.responses.merge.fhir_merge_resource_response import (
    FhirMergeResourceResponse,
)
from helix_fhir_client_sdk.responses.merge.fhir_merge_resource_response_entry import (
    FhirMergeResourceResponseEntry,
)
from helix_fhir_client_sdk.responses.merge.fhir_merge_response_entry_issue import (
    FhirMergeResponseEntryError,
)
from helix_fhir_client_sdk.structures.get_access_token_result import (
    GetAccessTokenResult,
)
from helix_fhir_client_sdk.utilities.fhir_client_logger import FhirClientLogger
from helix_fhir_client_sdk.utilities.retryable_aiohttp_client import (
    RetryableAioHttpClient,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_response import (
    RetryableAioHttpResponse,
)
from helix_fhir_client_sdk.validators.async_fhir_validator import AsyncFhirValidator


class FhirMergeResourcesMixin(FhirClientProtocol):
    async def merge_bundle_uncompressed(
        self,
        id_: str | None,
        bundle: FhirBundle,
    ) -> FhirMergeResourceResponse:
        """
        Optimized variant of :meth:`merge_bundle_async` that bypasses storage-mode handling.
        Use this method when you do not need storage-mode behavior, or features such as request/response compression.
        :param id_: id of the resource to merge
        :param bundle: FHIR Bundle to merge
        :return: FhirMergeResourceResponse
        """
        # Initialize profiling dictionary
        profiling: dict[str, float] = {
            "total_time": 0.0,
            "build_url": 0.0,
            "get_access_token": 0.0,
            "prepare_payload": 0.0,
            "http_post": 0.0,
            "parse_response": 0.0,
            "create_response_objects": 0.0,
        }

        merge_start_time = time.time()

        request_id: str | None = None
        response_status: int = 500

        # Build URL
        build_url_start = time.time()
        full_uri: furl = furl(self._url)
        full_uri /= self._resource

        # Prepare headers
        headers = {"Content-Type": "application/fhir+json"}
        headers.update(self._additional_request_headers)
        profiling["build_url"] = time.time() - build_url_start

        # Get access token
        get_token_start = time.time()
        access_token_result: GetAccessTokenResult = await self.get_access_token_async()
        access_token: str | None = access_token_result.access_token
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        profiling["get_access_token"] = time.time() - get_token_start

        # Prepare JSON payload
        prepare_payload_start = time.time()
        first_resource: FhirResource | None = bundle.entry[0].resource
        assert first_resource is not None
        json_payload: str = first_resource.json() if len(bundle.entry) == 1 else bundle.json()

        # Build merge URL
        obj_id: str = id_ or "1"
        resource_uri: furl = full_uri / parse.quote(str(obj_id), safe="") / "$merge"
        profiling["prepare_payload"] = time.time() - prepare_payload_start

        response_text: str | None = None
        responses: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        try:
            async with RetryableAioHttpClient(
                fn_get_session=self.create_http_session,
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
                http_post_start = time.time()
                response: RetryableAioHttpResponse = await client.post(
                    url=resource_uri.url,
                    data=json_payload,
                    headers=headers,
                )
                profiling["http_post"] = time.time() - http_post_start

                response_status = response.status
                request_id = response.response_headers.get("X-Request-ID", None)

                parse_response_start = time.time()
                if response.status == 200:
                    response_text = await response.get_text_async()
                    if response_text:
                        try:
                            # Parse response as plain dicts for speed
                            parsed_response = json.loads(response_text)
                            if isinstance(parsed_response, list):
                                responses = parsed_response
                            else:
                                responses = [parsed_response]
                        except (ValueError, json.JSONDecodeError) as e:
                            errors.append(
                                {
                                    "issue": [
                                        {
                                            "severity": "error",
                                            "code": "exception",
                                            "diagnostics": f"Failed to parse response: {str(e)}",
                                        }
                                    ]
                                }
                            )
                else:
                    # HTTP error
                    response_text = await response.get_text_async()
                    errors.append(
                        {
                            "issue": [
                                {
                                    "severity": "error",
                                    "code": "exception",
                                    "diagnostics": response_text or f"HTTP {response.status}",
                                }
                            ]
                        }
                    )
                profiling["parse_response"] = time.time() - parse_response_start

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
                elapsed_time=time.time() - merge_start_time,
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
                elapsed_time=time.time() - merge_start_time,
            ) from e

        # Convert dict responses to proper objects using fast method
        create_objects_start = time.time()
        response_entries: deque[BaseFhirMergeResourceResponseEntry] = deque()

        for resp_dict in responses:
            response_entries.append(FhirMergeResourceResponseEntry.from_dict_uncompressed(resp_dict))

        for error_dict in errors:
            response_entries.append(FhirMergeResponseEntryError.from_dict(error_dict, storage_mode=self._storage_mode))
        profiling["create_response_objects"] = time.time() - create_objects_start

        profiling["total_time"] = time.time() - merge_start_time

        # Log profiling information if logger is available
        if self._logger:
            self._logger.debug(
                f"merge_bundle_without_storage profiling: "
                f"total={profiling['total_time']:.3f}s, "
                f"build_url={profiling['build_url']:.3f}s, "
                f"get_token={profiling['get_access_token']:.3f}s, "
                f"prepare_payload={profiling['prepare_payload']:.3f}s, "
                f"http_post={profiling['http_post']:.3f}s, "
                f"parse_response={profiling['parse_response']:.3f}s, "
                f"create_objects={profiling['create_response_objects']:.3f}s"
            )

        return FhirMergeResourceResponse(
            request_id=request_id,
            url=resource_uri.url,
            responses=response_entries,
            error=None if response_status == 200 else (response_text or f"HTTP {response_status}"),
            access_token=self._access_token,
            status=response_status,
            response_text=response_text,
        )

    async def merge_bundle_async(
        self,
        id_: str | None,
        bundle: FhirBundle,
    ) -> AsyncGenerator[FhirMergeResourceResponse, None]:
        """
        Calls $merge function on FHIR server


        :param bundle: FHIR Bundle
        :param id_: id of the resource to merge
        :param bundle: FHIR Bundle to merge
        :return: response
        """
        assert self._url, "No FHIR server url was set"
        assert isinstance(
            bundle,
            FhirBundle,
        ), f"Expected FhirResourceList, got {type(bundle)}"

        self._internal_logger.debug(
            f"Calling $merge on {self._url} with client_id={self._client_id} and scopes={self._auth_scopes}"
        )
        instance_variables_text = convert_dict_to_str(FhirClientLogger.get_variables_to_log(vars(self)))
        if self._internal_logger:
            self._internal_logger.debug(f"parameters: {instance_variables_text}")
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

        start_time: float = time.time()
        # set access token in request if present
        access_token_result: GetAccessTokenResult = await self.get_access_token_async()
        access_token: str | None = access_token_result.access_token
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        validation_errors: deque[BaseFhirMergeResourceResponseEntry] = deque()
        try:
            # If we found some resources
            if len(bundle.entry) > 0:
                responses: list[BaseFhirMergeResourceResponseEntry] = []
                errors: list[FhirMergeResponseEntryError] = []
                resource_uri: furl = full_uri.copy()
                # if there is only item in the list then send it instead of having it in a list
                first_resource: FhirResource | None = bundle.entry[0].resource
                assert isinstance(first_resource, FhirResource)
                assert first_resource is not None
                json_payload: str = first_resource.json() if len(bundle.entry) == 1 else bundle.json()
                # json_payload_bytes: str = json_payload
                obj_id: str = id_ or "1"  # TODO: remove this once the node fhir accepts merge without a parameter
                assert obj_id

                resource_uri /= parse.quote(str(obj_id), safe="")
                resource_uri /= "$merge"
                response_text: str | None = None
                try:
                    async with RetryableAioHttpClient(
                        fn_get_session=self._fn_create_http_session or self.create_http_session,
                        caller_managed_session=self._fn_create_http_session is not None,
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
                        self._internal_logger.debug(f"X-Request-ID={request_id}")
                        if response and response.status == 200:
                            response_text = await response.get_text_async()
                            if response_text:
                                try:
                                    responses.extend(
                                        FhirMergeResourceResponseEntry.from_json(
                                            response_text,
                                            storage_mode=self._storage_mode,
                                        )
                                    )
                                except ValueError as e:
                                    errors.append(
                                        FhirMergeResponseEntryError.from_dict(
                                            {
                                                "issue": [
                                                    {
                                                        "severity": "error",
                                                        "code": "exception",
                                                        "diagnostics": str(e),
                                                    }
                                                ]
                                            },
                                            storage_mode=self._storage_mode,
                                        )
                                    )

                            all_responses: deque[BaseFhirMergeResourceResponseEntry] = deque(
                                list(responses) + list(errors)
                            )
                            yield FhirMergeResourceResponse(
                                request_id=request_id,
                                url=resource_uri.url,
                                responses=all_responses,
                                error=(
                                    json.dumps([r.to_dict() for r in responses] + [e.to_dict() for e in errors])
                                    if response_status != 200
                                    else None
                                ),
                                access_token=self._access_token,
                                status=response_status if response_status else 500,
                                response_text=json_payload,
                            )
                        else:  # other HTTP errors
                            self._internal_logger.info(f"POST response for {resource_uri.url}: {response.status}")
                            response_text = await response.get_text_async()
                            yield FhirMergeResourceResponse(
                                request_id=request_id,
                                url=resource_uri.url or self._url or "",
                                response_text=json_payload,
                                responses=deque(
                                    [
                                        FhirMergeResourceResponseEntry.from_dict(
                                            {
                                                "issue": [
                                                    {
                                                        "severity": "error",
                                                        "code": "exception",
                                                        "diagnostics": response_text,
                                                    }
                                                ]
                                            },
                                            storage_mode=self._storage_mode,
                                        )
                                    ]
                                ),
                                error=(response_text if response_text else None),
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
                yield FhirMergeResourceResponse(
                    request_id=request_id,
                    url=full_uri.url,
                    responses=validation_errors,
                    error="No resources to send",
                    access_token=self._access_token,
                    status=response_status if response_status else 500,
                    response_text=None,
                )
        except AssertionError as e:
            if self._logger:
                self._logger.error(
                    Exception(
                        f"Assertion: FHIR send failed: {str(e)} for bundle: {bundle.json()}. "
                        + f"variables={convert_dict_to_str(FhirClientLogger.get_variables_to_log(vars(self)))}"
                    )
                )
            raise e

    async def merge_resources_async(
        self,
        id_: str | None,
        resources_to_merge: FhirResourceList,
        batch_size: int | None,
    ) -> AsyncGenerator[FhirMergeResourceResponse, None]:
        """
        Calls $merge function on FHIR server


        :param resources_to_merge: list of resources to send
        :param id_: id of the resource to merge
        :param batch_size: size of each batch
        :return: response
        """
        assert self._url, "No FHIR server url was set"
        assert isinstance(resources_to_merge, FhirResourceList), (
            f"Expected FhirResourceList, got {type(resources_to_merge)}"
        )

        self._internal_logger.debug(
            f"Calling $merge on {self._url} with client_id={self._client_id} and scopes={self._auth_scopes}"
        )
        instance_variables_text = convert_dict_to_str(FhirClientLogger.get_variables_to_log(vars(self)))
        if self._internal_logger:
            self._internal_logger.debug(f"parameters: {instance_variables_text}")
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

        start_time: float = time.time()
        # set access token in request if present
        access_token_result: GetAccessTokenResult = await self.get_access_token_async()
        access_token: str | None = access_token_result.access_token
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        validation_errors: deque[BaseFhirMergeResourceResponseEntry] = deque()
        try:
            resource_json_list_clean: FhirResourceList
            if self._validation_server_url:
                (
                    resource_json_list_clean,
                    validation_errors,
                ) = await self.validate_resource(
                    resources_to_validate=resources_to_merge,
                )
            else:
                resource_json_list_clean = resources_to_merge

            # If we found some resources
            if len(resource_json_list_clean) > 0:
                resource_batch: FhirResourceList
                async for resource_batch in resource_json_list_clean.consume_resource_batch_async(
                    batch_size=batch_size
                ):
                    responses: list[BaseFhirMergeResourceResponseEntry] = []
                    errors: list[FhirMergeResponseEntryError] = []
                    resource_uri: furl = full_uri.copy()
                    # if there is only item in the list then send it instead of having it in a list
                    json_payload: str = resource_batch[0].json() if len(resource_batch) == 1 else resource_batch.json()
                    # json_payload_bytes: str = json_payload
                    obj_id: str = id_ or "1"  # TODO: remove this once the node fhir accepts merge without a parameter
                    assert obj_id

                    resource_uri /= parse.quote(str(obj_id), safe="")
                    resource_uri /= "$merge"
                    response_text: str | None = None
                    try:
                        async with RetryableAioHttpClient(
                            fn_get_session=self._fn_create_http_session or self.create_http_session,
                            caller_managed_session=self._fn_create_http_session is not None,
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
                            self._internal_logger.debug(f"X-Request-ID={request_id}")
                            if response and response.status == 200:
                                response_text = await response.get_text_async()
                                if response_text:
                                    try:
                                        responses.extend(
                                            FhirMergeResourceResponseEntry.from_json(
                                                response_text,
                                                storage_mode=self._storage_mode,
                                            )
                                        )
                                    except ValueError as e:
                                        errors.append(
                                            FhirMergeResponseEntryError.from_dict(
                                                {
                                                    "issue": [
                                                        {
                                                            "severity": "error",
                                                            "code": "exception",
                                                            "diagnostics": str(e),
                                                        }
                                                    ]
                                                },
                                                storage_mode=self._storage_mode,
                                            )
                                        )

                                all_responses: deque[BaseFhirMergeResourceResponseEntry] = deque(
                                    list(responses) + list(errors)
                                )
                                yield FhirMergeResourceResponse(
                                    request_id=request_id,
                                    url=resource_uri.url,
                                    responses=all_responses,
                                    error=(
                                        json.dumps([r.to_dict() for r in responses] + [e.to_dict() for e in errors])
                                        if response_status != 200
                                        else None
                                    ),
                                    access_token=self._access_token,
                                    status=response_status if response_status else 500,
                                    response_text=json_payload,
                                )
                            else:  # other HTTP errors
                                self._internal_logger.info(f"POST response for {resource_uri.url}: {response.status}")
                                response_text = await response.get_text_async()
                                yield FhirMergeResourceResponse(
                                    request_id=request_id,
                                    url=resource_uri.url or self._url or "",
                                    response_text=json_payload,
                                    responses=deque(
                                        [
                                            FhirMergeResourceResponseEntry.from_dict(
                                                {
                                                    "issue": [
                                                        {
                                                            "severity": "error",
                                                            "code": "exception",
                                                            "diagnostics": response_text,
                                                        }
                                                    ]
                                                },
                                                storage_mode=self._storage_mode,
                                            )
                                        ]
                                    ),
                                    error=(response_text if response_text else None),
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
                yield FhirMergeResourceResponse(
                    request_id=request_id,
                    url=full_uri.url,
                    responses=validation_errors,
                    error="No resources to send",
                    access_token=self._access_token,
                    status=response_status if response_status else 500,
                    response_text=None,
                )
        except AssertionError as e:
            if self._logger:
                self._logger.error(
                    Exception(
                        f"Assertion: FHIR send failed: {str(e)} for resource: {resources_to_merge.json()}. "
                        + f"variables={convert_dict_to_str(FhirClientLogger.get_variables_to_log(vars(self)))}"
                    )
                )
            raise e

    async def validate_resource(
        self,
        *,
        resources_to_validate: FhirResourceList,
    ) -> tuple[FhirResourceList, deque[BaseFhirMergeResourceResponseEntry]]:
        """
        Calls the validation server to validate the content of a resource

        :param resources_to_validate: the resources to validate
        :returns: the validated resources, the list of errors
        """
        errors: deque[BaseFhirMergeResourceResponseEntry] = deque()
        resource_json_list_clean: FhirResourceList = FhirResourceList()
        assert self._validation_server_url
        # if there is only resource then just validate that individually
        if len(resources_to_validate) == 1:
            resource: FhirResource = resources_to_validate[0]
            try:
                with resource.transaction():
                    access_token_result: GetAccessTokenResult = await self.get_access_token_async()
                    access_token: str | None = access_token_result.access_token

                    await AsyncFhirValidator.validate_fhir_resource(
                        fn_get_session=self._fn_create_http_session or self.create_http_session,
                        json_data=resource.json(),
                        resource_name=cast(str | None, resource.get("resourceType")) or self._resource or "",
                        validation_server_url=self._validation_server_url,
                        access_token=access_token,
                        caller_managed_session=self._fn_create_http_session is not None,
                    )
                    resource_json_list_clean.append(resource)
            except FhirValidationException as e:
                errors.append(
                    FhirMergeResponseEntryError(
                        id_=resource.id,
                        resource_type=resource.resource_type,
                        issue=e.issue,
                        status=400,
                        error="Validation error",
                        token=access_token,
                    )
                )
        else:
            access_token_result1: GetAccessTokenResult = await self.get_access_token_async()
            access_token1: str | None = access_token_result1.access_token
            for resource in resources_to_validate:
                try:
                    with resource.transaction():
                        await AsyncFhirValidator.validate_fhir_resource(
                            fn_get_session=self._fn_create_http_session or self.create_http_session,
                            json_data=resource.json(),
                            resource_name=resource.get("resourceType") or self._resource or "",
                            validation_server_url=self._validation_server_url,
                            access_token=access_token1,
                            caller_managed_session=self._fn_create_http_session is not None,
                        )
                        resource_json_list_clean.append(resource)
                except FhirValidationException as e:
                    errors.append(
                        FhirMergeResponseEntryError(
                            id_=resource.id,
                            resource_type=resource.resource_type,
                            issue=e.issue,
                            status=400,
                            error="Validation error",
                            token=access_token1,
                        )
                    )
        return resource_json_list_clean, errors
