import json
from typing import Optional, Dict, Any, List, Union, override

from helix_fhir_client_sdk.fhir_bundle import (
    BundleEntry,
)
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder
from helix_fhir_client_sdk.utilities.retryable_aiohttp_url_result import (
    RetryableAioHttpUrlResult,
)


class FhirGetListByResourceTypeResponse(FhirGetResponse):
    """
    This class represents a response from a FHIR server.
    NOTE: This class does converted to a Row in Spark so keep all the property types simple python types


    """

    def __init__(
        self,
        *,
        request_id: Optional[str],
        url: str,
        resources: List[Dict[str, Any]],
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
    ) -> None:
        super().__init__(
            request_id=request_id,
            url=url,
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
        )
        self._resource_map: Dict[str, List[Dict[str, Any]]] = (
            self._parse_into_resource_map(resources=resources)
        )

    @override
    def _append(self, other_response: "FhirGetResponse") -> "FhirGetResponse":
        """
        Append the responses from other to self

        :param other_response: FhirGetResponse object to append to current one
        :return: self
        """

        for resource in other_response.get_resources():
            resource_type = resource.get("resourceType")
            if resource_type:
                if resource_type not in self._resource_map:
                    self._resource_map[resource_type] = []
                self._resource_map[resource_type].append(resource)

        return self

    @override
    def _extend(self, others: List["FhirGetResponse"]) -> "FhirGetResponse":
        """
        Append the responses from other to self

        :param others: list of FhirGetResponse objects
        :return: self
        """
        for other_response in others:
            self.append(other_response=other_response)

        return self

    @override
    def get_resources(self) -> List[Dict[str, Any]]:
        """
        Gets the resources from the response


        :return: list of resources
        """

        return [c.resource for c in self.get_bundle_entries() if c.resource is not None]

    @override
    def get_bundle_entries(self) -> List[BundleEntry]:
        raise NotImplementedError(
            "get_bundle_entries is not implemented for FhirGetListByResourceTypeResponse. "
        )

    @classmethod
    def _parse_resources(cls, *, responses: str) -> List[Dict[str, Any]]:
        """
        Gets the resources from the response


        :return: list of resources
        """
        try:
            # THis is either a list of resources or a Bundle resource containing a list of resources
            child_response_resources: Dict[str, Any] | List[Dict[str, Any]] = (
                cls.parse_json(responses)
            )
            assert isinstance(child_response_resources, list)
            return child_response_resources
        except Exception as e:
            raise Exception(f"Could not get resources from: {responses}") from e

    @override
    def remove_duplicates(self) -> FhirGetResponse:
        """
        removes duplicate resources from the response i.e., resources with same resourceType and id

        """
        raise NotImplementedError(
            "Remove duplicates is not implemented for FhirGetListByResourceTypeResponse. "
        )

    @classmethod
    @override
    def from_response(cls, other_response: "FhirGetResponse") -> "FhirGetResponse":
        if isinstance(other_response, FhirGetListByResourceTypeResponse):
            return other_response

        response: FhirGetListByResourceTypeResponse = FhirGetListByResourceTypeResponse(
            request_id=other_response.request_id,
            url=other_response.url,
            resources=other_response.get_resources(),
            error=other_response.error,
            access_token=other_response.access_token,
            total_count=other_response.total_count,
            status=other_response.status,
            next_url=other_response.next_url,
            extra_context_to_return=other_response.extra_context_to_return,
            resource_type=other_response.resource_type,
            id_=other_response.id_,
            response_headers=other_response.response_headers,
            chunk_number=other_response.chunk_number,
            cache_hits=other_response.cache_hits,
            results_by_url=other_response.results_by_url,
        )
        return response

    @override
    def get_response_text(self) -> str:
        """
        Gets the response text from the response

        :return: response text
        """
        return json.dumps(self._resource_map, cls=FhirJSONEncoder)

    @classmethod
    def _parse_into_resource_map(
        cls, resources: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        resource_map: Dict[str, List[Dict[str, Any]]] = {}
        resource: Dict[str, Any]
        for resource in resources:
            if resource:
                resource_type = resource.get("resourceType")
                assert resource_type, f"No resourceType in {json.dumps(resource)}"
                if resource_type not in resource_map:
                    resource_map[resource_type] = []

                resource_map[resource_type].append(resource)
        return resource_map

    @override
    def sort_resources(self) -> "FhirGetListByResourceTypeResponse":
        return self
