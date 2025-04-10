import json
from typing import Optional, Dict, Any, Union, List

from helix_fhir_client_sdk.responses.get.fhir_get_bundle_response import (
    FhirGetBundleResponse,
)
from helix_fhir_client_sdk.responses.get.fhir_get_error_response import (
    FhirGetErrorResponse,
)
from helix_fhir_client_sdk.responses.get.fhir_get_list_response import (
    FhirGetListResponse,
)
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.get.fhir_get_single_response import (
    FhirGetSingleResponse,
)
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
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
        request_id: Optional[str],
        url: str,
        response_text: str,
        error: Optional[str],
        access_token: Optional[str],
        total_count: Optional[int],
        status: int,
        next_url: Optional[str] = None,
        extra_context_to_return: Optional[Dict[str, Any]],
        resource_type: Optional[str],
        id_: Optional[Union[List[str], str]],
        response_headers: Optional[
            List[str]
        ],  # header name and value separated by a colon
        chunk_number: Optional[int] = None,
        cache_hits: Optional[int] = None,
        results_by_url: List[RetryableAioHttpUrlResult],
        storage_mode: CompressedDictStorageMode,
        create_operation_outcome_for_error: Optional[bool],
    ) -> FhirGetResponse:

        if not error and response_text:
            # test if responses is valid json
            try:
                # Attempt to parse the JSON response
                json.loads(response_text)
            except ValueError as e:
                error = f"Error parsing response: {response_text}: {e}"

        if status != 200 or error:
            # If the status is not 200, return a single response with the error
            return FhirGetErrorResponse(
                request_id=request_id,
                url=url,
                response_text=response_text,
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

        child_response_resources: Dict[str, Any] | List[Dict[str, Any]] = (
            FhirGetResponse.parse_json(response_text)
        )

        # first see if it is just a list of resources
        if isinstance(child_response_resources, list):
            return FhirGetListResponse(
                request_id=request_id,
                url=url,
                response_text=response_text,
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
                response_text=response_text,
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
            response_text=response_text,
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
