import json
from typing import Optional, Dict, Any, List, Union, override, AsyncGenerator, cast

from helix_fhir_client_sdk.fhir_bundle import (
    BundleEntry,
    BundleEntryRequest,
    BundleEntryResponse,
)
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.get_responses.fhir_get_bundle_response import (
    FhirGetBundleResponse,
)
from helix_fhir_client_sdk.structures.fhir_types import FhirResource
from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder
from helix_fhir_client_sdk.utilities.retryable_aiohttp_url_result import (
    RetryableAioHttpUrlResult,
)


class FhirGetSingleResponse(FhirGetResponse):
    """
    This class represents a response from a FHIR server.
    NOTE: This class does converted to a Row in Spark so keep all the property types simple python types


    """

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
        self._resource: Optional[Dict[str, Any]] = self._parse_single_resource(
            responses=response_text
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
    def get_resources(self) -> List[Dict[str, Any]]:
        """
        Gets the resources from the response


        :return: list of resources
        """
        if not self._resource:
            return []

        return [self._resource] if self._resource else []

    def get_bundle_entry(self) -> BundleEntry:
        # use these if the bundle entry does not have them
        request: BundleEntryRequest = BundleEntryRequest(url=self.url)
        response: BundleEntryResponse = BundleEntryResponse(
            status=str(self.status),
            lastModified=self.lastModified,
            etag=self.etag,
        )
        bundle_entry = BundleEntry(
            resource=self._resource, request=request, response=response
        )
        return bundle_entry

    @override
    def get_bundle_entries(self) -> List[BundleEntry]:
        """
        Gets the Bundle entries from the response


        :return: list of bundle entries
        """
        if not self._resource:
            return []
        try:
            return [self.get_bundle_entry()]
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
    def _parse_single_resource(cls, *, responses: str) -> Dict[str, Any] | None:
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
            return child_response_resources
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
    async def get_resources_generator(self) -> AsyncGenerator[FhirResource, None]:
        yield cast(FhirResource, self._resource)

    @override
    async def get_bundle_entries_generator(self) -> AsyncGenerator[BundleEntry, None]:
        bundle_entry: BundleEntry = self.get_bundle_entry()
        yield bundle_entry
