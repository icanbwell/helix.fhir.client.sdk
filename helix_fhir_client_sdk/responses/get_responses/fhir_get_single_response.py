import json
from collections import deque
from typing import (
    Optional,
    Dict,
    Any,
    List,
    Union,
    override,
    AsyncGenerator,
    Deque,
)

from helix_fhir_client_sdk.fhir.bundle_entry import BundleEntry
from helix_fhir_client_sdk.fhir.bundle_entry_request import BundleEntryRequest
from helix_fhir_client_sdk.fhir.bundle_entry_response import BundleEntryResponse
from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.get_responses.fhir_get_bundle_response import (
    FhirGetBundleResponse,
)
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder
from helix_fhir_client_sdk.utilities.retryable_aiohttp_url_result import (
    RetryableAioHttpUrlResult,
)


class FhirGetSingleResponse(FhirGetResponse):
    """
    This class represents a response from a FHIR server.
    NOTE: This class does converted to a Row in Spark so keep all the property types simple python types


    """

    __slots__ = FhirGetResponse.__slots__ + [
        # Specific to this subclass
        "_resource"
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
        self._resource: Optional[FhirResource] = self._parse_single_resource(
            responses=response_text, storage_mode=storage_mode
        )

    @override
    def _append(self, other_response: "FhirGetResponse") -> "FhirGetResponse":
        """
        Append the responses from other to self

        :param other_response: FhirGetResponse object to append to current one
        :return: self
        """
        # if someone is trying to append to a single resource then we need to convert it to a bundle
        return FhirGetBundleResponse.from_response(other_response=self).append(
            other_response=other_response
        )

    @override
    def _extend(self, others: List["FhirGetResponse"]) -> "FhirGetResponse":
        """
        Append the responses from other to self

        :param others: list of FhirGetResponse objects
        :return: self
        """
        # if someone is trying to append to a single resource then we need to convert it to a bundle
        return FhirGetBundleResponse.from_response(other_response=self).extend(
            others=others
        )

    @override
    def get_resources(self) -> Deque[FhirResource]:
        """
        Gets the resources from the response


        :return: list of resources
        """
        if not self._resource:
            return deque()

        return deque([self._resource]) if self._resource else deque()

    def _create_bundle_entry(self, *, resource: FhirResource) -> BundleEntry:
        # use these if the bundle entry does not have them
        request: BundleEntryRequest = BundleEntryRequest(url=self.url)
        response: BundleEntryResponse = BundleEntryResponse(
            status=str(self.status),
            lastModified=self.lastModified,
            etag=self.etag,
        )
        bundle_entry = BundleEntry(
            resource=resource,
            request=request,
            response=response,
            storage_mode=self.storage_mode,
        )
        return bundle_entry

    @override
    def get_bundle_entries(self) -> Deque[BundleEntry]:
        """
        Gets the Bundle entries from the response


        :return: list of bundle entries
        """
        if not self._resource:
            return deque()
        try:
            return deque([self._create_bundle_entry(resource=self._resource)])
        except Exception as e:
            raise Exception(
                f"Could not get bundle entries from: {self._resource}"
            ) from e

    @override
    def remove_duplicates(self) -> FhirGetResponse:
        """
        removes duplicate resources from the response i.e., resources with same resourceType and id

        """
        return self  # nothing to do since this is a single resource

    @classmethod
    def _parse_single_resource(
        cls, *, responses: str, storage_mode: CompressedDictStorageMode
    ) -> FhirResource | None:
        """
        Gets the single resource from the response

        :return: single resource
        """
        if not responses:
            return None
        try:
            child_response_resources: Dict[str, Any] | List[Dict[str, Any]] = (
                cls.parse_json(responses)
            )
            assert isinstance(child_response_resources, dict)
            return FhirResource(
                initial_dict=child_response_resources, storage_mode=storage_mode
            )
        except Exception as e:
            raise Exception(f"Could not get resources from: {responses}") from e

    @classmethod
    @override
    def from_response(cls, other_response: "FhirGetResponse") -> "FhirGetResponse":
        raise NotImplementedError(
            "FhirSingleGetResponse does not support from_response()"
        )

    @override
    def get_response_text(self) -> str:
        """
        Gets the response text from the response

        :return: response text
        """
        return json.dumps(self._resource, cls=FhirJSONEncoder)

    @override
    def sort_resources(self) -> "FhirGetSingleResponse":
        return self

    @override
    async def consume_resource(self) -> AsyncGenerator[FhirResource, None]:
        if self._resource:
            resource = self._resource
            self._resource = None
            yield resource

    @override
    async def consume_bundle_entry(self) -> AsyncGenerator[BundleEntry, None]:
        if self._resource:
            resource = self._resource
            self._resource = None
            yield self._create_bundle_entry(resource=resource)

    @override
    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the object to a dictionary

        :return: dictionary
        """
        return dict(
            request_id=self.request_id,
            _resource=self._resource.to_dict() if self._resource else None,
            url=self.url,
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
        return 1 if self._resource else 0
