import json
from typing import Any, cast

from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)

from helix_fhir_client_sdk.exceptions.fhir_get_exception import FhirGetException
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.get.fhir_get_bundle_response import (
    FhirGetBundleResponse,
)
from helix_fhir_client_sdk.responses.get.fhir_get_error_response import (
    FhirGetErrorResponse,
)
from helix_fhir_client_sdk.responses.get.fhir_get_list_response import (
    FhirGetListResponse,
)
from helix_fhir_client_sdk.responses.get.fhir_get_single_response import (
    FhirGetSingleResponse,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_url_result import (
    RetryableAioHttpUrlResult,
)


class FhirGetResponseFactory:
    """
    Factory class to create FHIR Get responses.
    """

    @staticmethod
    def create(
        *,
        request_id: str | None,
        url: str,
        response_text: str,
        error: str | None,
        access_token: str | None,
        total_count: int | None,
        status: int,
        next_url: str | None = None,
        extra_context_to_return: dict[str, Any] | None,
        resource_type: str | None,
        id_: list[str] | str | None,
        response_headers: list[str] | None,  # header name and value separated by a colon
        chunk_number: int | None = None,
        cache_hits: int | None = None,
        results_by_url: list[RetryableAioHttpUrlResult],
        storage_mode: CompressedDictStorageMode,
        create_operation_outcome_for_error: bool | None,
    ) -> FhirGetResponse:
        parsed_json: dict[str, Any] | list[dict[str, Any]] | None = None
        try:
            if not error and response_text:
                # test if responses is valid json; the parsed value is reused below so the text is parsed only once
                try:
                    # Attempt to parse the JSON response
                    parsed_json = json.loads(response_text)
                except ValueError as e:
                    error = f"Error parsing response: {response_text}: {e}"
        except Exception as e:
            raise FhirGetResponseFactory._create_exception(
                e=e,
                request_id=request_id,
                url=url,
                response_text=response_text,
                error=error,
                total_count=total_count,
                status=status,
                next_url=next_url,
                extra_context_to_return=extra_context_to_return,
                resource_type=resource_type,
                id_=id_,
                chunk_number=chunk_number,
                cache_hits=cache_hits,
            ) from e

        return FhirGetResponseFactory._create(
            request_id=request_id,
            url=url,
            response_text=response_text,
            parsed_json=parsed_json,
            error=error,
            access_token=access_token,
            total_count=total_count,
            status=status,
            next_url=next_url,
            extra_context_to_return=extra_context_to_return,
            resource_type=resource_type,
            id_=id_,
            response_headers=response_headers,
            chunk_number=chunk_number,
            cache_hits=cache_hits,
            results_by_url=results_by_url,
            storage_mode=storage_mode,
            create_operation_outcome_for_error=create_operation_outcome_for_error,
        )

    @staticmethod
    def create_from_parsed_json(
        *,
        request_id: str | None,
        url: str,
        parsed_json: dict[str, Any] | list[dict[str, Any]],
        error: str | None,
        access_token: str | None,
        total_count: int | None,
        status: int,
        next_url: str | None = None,
        extra_context_to_return: dict[str, Any] | None,
        resource_type: str | None,
        id_: list[str] | str | None,
        response_headers: list[str] | None,  # header name and value separated by a colon
        chunk_number: int | None = None,
        cache_hits: int | None = None,
        results_by_url: list[RetryableAioHttpUrlResult],
        storage_mode: CompressedDictStorageMode,
        create_operation_outcome_for_error: bool | None,
    ) -> FhirGetResponse:
        """
        Same as create() but takes JSON that has already been parsed, so callers that already hold the parsed
        response do not serialize it to text just for it to be parsed again.
        The result is the same as create(response_text=json.dumps(parsed_json), ...).
        The text is only built when it is needed (error responses).
        """
        return FhirGetResponseFactory._create(
            request_id=request_id,
            url=url,
            response_text=None,
            parsed_json=parsed_json,
            error=error,
            access_token=access_token,
            total_count=total_count,
            status=status,
            next_url=next_url,
            extra_context_to_return=extra_context_to_return,
            resource_type=resource_type,
            id_=id_,
            response_headers=response_headers,
            chunk_number=chunk_number,
            cache_hits=cache_hits,
            results_by_url=results_by_url,
            storage_mode=storage_mode,
            create_operation_outcome_for_error=create_operation_outcome_for_error,
        )

    @staticmethod
    def _create(
        *,
        request_id: str | None,
        url: str,
        response_text: str | None,
        parsed_json: dict[str, Any] | list[dict[str, Any]] | None,
        error: str | None,
        access_token: str | None,
        total_count: int | None,
        status: int,
        next_url: str | None,
        extra_context_to_return: dict[str, Any] | None,
        resource_type: str | None,
        id_: list[str] | str | None,
        response_headers: list[str] | None,
        chunk_number: int | None,
        cache_hits: int | None,
        results_by_url: list[RetryableAioHttpUrlResult],
        storage_mode: CompressedDictStorageMode,
        create_operation_outcome_for_error: bool | None,
    ) -> FhirGetResponse:
        """
        :param response_text: the response text, or None to build it from parsed_json only when it is needed
        :param parsed_json: the parsed response text, or None if response_text is empty or was not parsed
        """
        try:
            if status != 200 or error:
                # If the status is not 200, return a single response with the error
                return FhirGetErrorResponse(
                    request_id=request_id,
                    url=url,
                    response_text=(response_text if response_text is not None else json.dumps(parsed_json)),
                    error=error,
                    access_token=access_token,
                    total_count=total_count,
                    status=status,
                    next_url=next_url,
                    extra_context_to_return=extra_context_to_return,
                    resource_type=resource_type,
                    id_=id_,
                    response_headers=response_headers,
                    chunk_number=chunk_number,
                    cache_hits=cache_hits,
                    results_by_url=results_by_url,
                    storage_mode=storage_mode,
                    create_operation_outcome_for_error=create_operation_outcome_for_error,
                )

            child_response_resources: dict[str, Any] | list[dict[str, Any]] = (
                parsed_json if parsed_json is not None else FhirGetResponse.parse_json(response_text or "")
            )
            # the subclasses do not keep the text, so they only need it when there is no parsed value
            subclass_response_text: str = response_text or ""

            # first see if it is just a list of resources
            if isinstance(child_response_resources, list):
                return FhirGetListResponse(
                    request_id=request_id,
                    url=url,
                    response_text=subclass_response_text,
                    parsed_json=cast(list[dict[str, Any]] | None, parsed_json),
                    error=error,
                    access_token=access_token,
                    total_count=total_count,
                    status=status,
                    next_url=next_url,
                    extra_context_to_return=extra_context_to_return,
                    resource_type=resource_type,
                    id_=id_,
                    response_headers=response_headers,
                    chunk_number=chunk_number,
                    cache_hits=cache_hits,
                    results_by_url=results_by_url,
                    storage_mode=storage_mode,
                )

            # then check if it is a bundle
            if "entry" in child_response_resources or (
                "resourceType" in child_response_resources
                and child_response_resources["resourceType"].lower() == "bundle"
            ):
                return FhirGetBundleResponse(
                    request_id=request_id,
                    url=url,
                    response_text=subclass_response_text,
                    parsed_json=cast(dict[str, Any] | None, parsed_json),
                    error=error,
                    access_token=access_token,
                    total_count=total_count,
                    status=status,
                    next_url=next_url,
                    extra_context_to_return=extra_context_to_return,
                    resource_type=resource_type,
                    id_=id_,
                    response_headers=response_headers,
                    chunk_number=chunk_number,
                    cache_hits=cache_hits,
                    results_by_url=results_by_url,
                    storage_mode=storage_mode,
                )

            # now assume it is a single resource
            return FhirGetSingleResponse(
                request_id=request_id,
                url=url,
                response_text=subclass_response_text,
                parsed_json=cast(dict[str, Any] | None, parsed_json),
                error=error,
                access_token=access_token,
                total_count=total_count,
                status=status,
                next_url=next_url,
                extra_context_to_return=extra_context_to_return,
                resource_type=resource_type,
                id_=id_,
                response_headers=response_headers,
                chunk_number=chunk_number,
                cache_hits=cache_hits,
                results_by_url=results_by_url,
                storage_mode=storage_mode,
            )
        except Exception as e:
            raise FhirGetResponseFactory._create_exception(
                e=e,
                request_id=request_id,
                url=url,
                response_text=(response_text if response_text is not None else json.dumps(parsed_json)),
                error=error,
                total_count=total_count,
                status=status,
                next_url=next_url,
                extra_context_to_return=extra_context_to_return,
                resource_type=resource_type,
                id_=id_,
                chunk_number=chunk_number,
                cache_hits=cache_hits,
            ) from e

    @staticmethod
    def _create_exception(
        *,
        e: Exception,
        request_id: str | None,
        url: str,
        response_text: str,
        error: str | None,
        total_count: int | None,
        status: int,
        next_url: str | None,
        extra_context_to_return: dict[str, Any] | None,
        resource_type: str | None,
        id_: list[str] | str | None,
        chunk_number: int | None,
        cache_hits: int | None,
    ) -> FhirGetException:
        return FhirGetException(
            message="Error creating FHIR Get response",
            exception=e,
            request_id=request_id,
            url=url,
            headers=None,
            json_data=response_text,
            response_text=response_text,
            response_status_code=status,
            variables={
                "request_id": request_id,
                "url": url,
                "response_text": response_text,
                "error": error,
                "total_count": total_count,
                "status": status,
                "next_url": next_url,
                "extra_context_to_return": extra_context_to_return,
                "resource_type": resource_type,
                "id_": id_,
                "chunk_number": chunk_number,
                "cache_hits": cache_hits,
            },
        )
