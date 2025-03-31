import json
from collections import deque
from typing import Optional, Dict, Any, List, Union, override, AsyncGenerator, Deque

from helix_fhir_client_sdk.fhir.bundle_entry import BundleEntry
from helix_fhir_client_sdk.fhir.bundle_entry_request import BundleEntryRequest
from helix_fhir_client_sdk.fhir.bundle_entry_response import BundleEntryResponse
from helix_fhir_client_sdk.fhir_bundle_appender import FhirBundleAppender
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder
from helix_fhir_client_sdk.utilities.retryable_aiohttp_url_result import (
    RetryableAioHttpUrlResult,
)


class FhirGetListResponse(FhirGetResponse):
    """
    This class represents a response from a FHIR server.
    NOTE: This class does converted to a Row in Spark so keep all the property types simple python types


    """

    __slots__ = FhirGetResponse.__slots__ + [
        # Specific to this subclass
        "_resources",
    ]

    def __init__(
        self,
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
        self._resources: Optional[Deque[FhirResource]] = self._parse_resources(
            responses=response_text, storage_mode=storage_mode
        )

    @override
    def _append(self, other_response: "FhirGetResponse") -> "FhirGetResponse":
        """
        Append the responses from other to self

        :param other_response: FhirGetResponse object to append to current one
        :return: self
        """
        if self._resources is None:
            self._resources = other_response.get_resources()
        else:
            self._resources.extend(other_response.get_resources())

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

    def get_resources(self) -> Deque[FhirResource]:
        return self._resources if self._resources else deque()

    @classmethod
    def _parse_resources(
        cls, *, responses: str, storage_mode: CompressedDictStorageMode
    ) -> Deque[FhirResource]:
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
            result: Deque[FhirResource] = deque()
            for r in child_response_resources:
                result.append(FhirResource(initial_dict=r, storage_mode=storage_mode))
            return result
        except Exception as e:
            raise Exception(f"Could not get resources from: {responses}") from e

    def get_bundle_entries(self) -> Deque[BundleEntry]:
        """
        Gets the Bundle entries from the response


        :return: list of bundle entries
        """
        if not self._resources:
            return deque()
        try:
            # THis is either a list of resources or a Bundle resource containing a list of resources

            result: Deque[BundleEntry] = deque()
            for resource in self._resources:
                entry: BundleEntry = self._create_bundle_entry(resource=resource)
                result.append(entry)
            return result
        except Exception as e:
            raise Exception(
                f"Could not get bundle entries from: {self._resources}"
            ) from e

    def _create_bundle_entry(self, *, resource: FhirResource) -> BundleEntry:
        # use these if the bundle entry does not have them
        request: BundleEntryRequest = BundleEntryRequest(url=self.url)
        response: BundleEntryResponse = BundleEntryResponse(
            status=str(self.status),
            lastModified=self.lastModified,
            etag=self.etag,
        )
        entry: BundleEntry = BundleEntry(
            resource=resource,
            request=request,
            response=response,
            storage_mode=self.storage_mode,
        )
        return entry

    def remove_duplicates(self) -> FhirGetResponse:
        """
        removes duplicate resources from the response i.e., resources with same resourceType and id

        """
        if not self._resources:
            return self  # nothing to do

        try:
            # if self._resources find unique entries by resourceType and id

            id_and_resource_dict: Dict[str, FhirResource] = {
                f'{r.get("resourceType")}/{r.get("id")}': r
                for r in self._resources
                if r.get("resourceType") and r.get("id")
            }

            unique_resources: List[FhirResource] = list(id_and_resource_dict.values())
            null_id_resources: List[FhirResource] = [
                r for r in self._resources if not r.get("id")
            ]
            unique_resources.extend(null_id_resources)
            self._resources = deque(unique_resources)
            return self
        except Exception as e:
            raise Exception(f"Could not get parse json from: {self._resources}") from e

    @classmethod
    @override
    def from_response(cls, other_response: "FhirGetResponse") -> "FhirGetResponse":
        if isinstance(other_response, FhirGetListResponse):
            return other_response

        resources: Deque[FhirResource] = other_response.get_resources()

        response: FhirGetListResponse = FhirGetListResponse(
            request_id=other_response.request_id,
            url=other_response.url,
            response_text=json.dumps(list(resources), cls=FhirJSONEncoder),
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
        response._resources = other_response.get_resources()
        return response

    @override
    def get_response_text(self) -> str:
        """
        Gets the response text from the response

        :return: response text
        """
        return (
            json.dumps([r for r in self._resources], cls=FhirJSONEncoder)
            if self._resources
            else "[]"
        )

    @override
    def sort_resources(self) -> "FhirGetListResponse":
        if self._resources:
            self._resources = FhirBundleAppender.sort_resources_in_list(
                resources=self._resources
            )
        return self

    @override
    async def consume_resource(self) -> AsyncGenerator[FhirResource, None]:
        while self._resources:
            yield self._resources.popleft()

    @override
    async def consume_bundle_entry(self) -> AsyncGenerator[BundleEntry, None]:
        while self._resources:
            resource: FhirResource = self._resources.popleft()
            yield self._create_bundle_entry(resource=resource)

    @override
    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the object to a dictionary

        :return: dictionary
        """
        return dict(
            request_id=self.request_id,
            url=self.url,
            _resources=(
                [r.to_dict() for r in self._resources] if self._resources else None
            ),
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
        return len(self._resources) if self._resources else 0
