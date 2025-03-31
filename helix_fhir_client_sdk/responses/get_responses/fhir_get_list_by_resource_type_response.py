import json
from typing import Optional, Dict, Any, List, Union, override, AsyncGenerator, Tuple

from helix_fhir_client_sdk.fhir.bundle_entry import (
    BundleEntry,
)
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder
from helix_fhir_client_sdk.utilities.retryable_aiohttp_url_result import (
    RetryableAioHttpUrlResult,
)


class FhirGetListByResourceTypeResponse(FhirGetResponse):
    """
    This class represents a response from a FHIR server.
    NOTE: This class does converted to a Row in Spark so keep all the property types simple python types


    """

    __slots__ = FhirGetResponse.__slots__ + [
        # Specific to this subclass
        "_resource_map",
        "_length",
    ]

    def __init__(
        self,
        *,
        request_id: Optional[str],
        url: str,
        resources: List[FhirResource],
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
            storage_mode=storage_mode,
        )
        count: int
        resource_map: Dict[str, List[FhirResource]]
        count, resource_map = self._parse_into_resource_map(resources=resources)
        self._resource_map: Dict[str, List[FhirResource]] = resource_map
        self._length: int = count

    @override
    def _append(self, other_response: "FhirGetResponse") -> "FhirGetResponse":
        """
        Append the responses from other to self

        :param other_response: FhirGetResponse object to append to current one
        :return: self
        """

        new_count: int = 0
        for resource in other_response.get_resources():
            resource_type = resource.get("resourceType")
            if resource_type:
                if resource_type not in self._resource_map:
                    self._resource_map[resource_type] = []
                self._resource_map[resource_type].append(resource)
                new_count += 1

        self._length += new_count
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
    def get_resources(self) -> List[FhirResource]:
        """
        Gets the resources from the response


        :return: list of resources
        """
        resources: List[FhirResource] = []
        resources_for_resource_type: List[FhirResource]
        for resources_for_resource_type in self._resource_map.values():
            resources.extend(resources_for_resource_type)

        return resources

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
            storage_mode=other_response.storage_mode,
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
        cls, resources: List[FhirResource]
    ) -> Tuple[int, Dict[str, List[FhirResource]]]:
        resource_map: Dict[str, List[FhirResource]] = {}
        resource: FhirResource
        count: int = 0
        for resource in resources:
            if resource:
                resource_type = resource.get("resourceType")
                assert resource_type, f"No resourceType in {json.dumps(resource)}"
                if resource_type not in resource_map:
                    resource_map[resource_type] = []

                count += 1
                resource_map[resource_type].append(resource)
        return count, resource_map

    @override
    def sort_resources(self) -> "FhirGetListByResourceTypeResponse":
        return self

    @override
    async def get_resources_generator(self) -> AsyncGenerator[FhirResource, None]:
        raise NotImplementedError(
            "get_resources_generator is not implemented for FhirGetListByResourceTypeResponse."
        )
        # noinspection PyUnreachableCode,PyTypeChecker
        yield None

    @override
    async def get_bundle_entries_generator(self) -> AsyncGenerator[BundleEntry, None]:
        raise NotImplementedError(
            "get_bundle_entries_generator is not implemented for FhirGetListByResourceTypeResponse."
        )
        # noinspection PyUnreachableCode,PyTypeChecker
        yield None

    def get_resource_map(self) -> Dict[str, List[FhirResource]]:
        """
        Gets the resource map from the response

        :return: resource map
        """
        return self._resource_map

    @override
    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the object to a dictionary

        :return: dictionary
        """
        return dict(
            request_id=self.request_id,
            url=self.url,
            response_text=self.get_response_text(),
            error=self.error,
            access_token=self.access_token,
            total_count=self.total_count,
            status=self.status,
            next_url=self.next_url,
            extra_context_to_return=self.extra_context_to_return,
            resource_type=self.resource_type,
            id_=self.id_,
            response_headers=self.response_headers,
            chunk_number=self.chunk_number,
            cache_hits=self.cache_hits,
            results_by_url=[r.to_dict() for r in self.results_by_url],
            storage_type=self.storage_mode.storage_type,
        )

    @override
    def get_resource_count(self) -> int:
        return self._length
