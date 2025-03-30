import json
from typing import Optional, Dict, Any, List, Union, override

from helix_fhir_client_sdk.fhir_bundle import (
    BundleEntry,
    BundleEntryRequest,
    BundleEntryResponse,
)
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.utilities.retryable_aiohttp_url_result import (
    RetryableAioHttpUrlResult,
)


class FhirGetListResponse(FhirGetResponse):
    """
    This class represents a response from a FHIR server.
    NOTE: This class does converted to a Row in Spark so keep all the property types simple python types


    """

    def __init__(
        self,
        *,
        request_id: Optional[str],
        url: str,
        responses: str,
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
        self._resources: Optional[List[Dict[str, Any]]] = self._parse_resources(
            responses=responses
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

    def get_resources(self) -> List[Dict[str, Any]]:
        return self._resources if self._resources else []

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

    def get_bundle_entries(self) -> List[BundleEntry]:
        """
        Gets the Bundle entries from the response


        :return: list of bundle entries
        """
        if not self._resources:
            return []
        try:
            # THis is either a list of resources or a Bundle resource containing a list of resources

            # use these if the bundle entry does not have them
            request: BundleEntryRequest = BundleEntryRequest(url=self.url)
            response: BundleEntryResponse = BundleEntryResponse(
                status=str(self.status),
                lastModified=self.lastModified,
                etag=self.etag,
            )
            return [
                BundleEntry(resource=r, request=request, response=response)
                for r in self.get_resources()
            ]
        except Exception as e:
            raise Exception(
                f"Could not get bundle entries from: {self._resources}"
            ) from e

    def remove_duplicates(self) -> None:
        """
        removes duplicate resources from the response i.e., resources with same resourceType and id

        """
        if not self._resources:
            return  # nothing to do

        try:
            unique_resources: List[Dict[str, Any]] = list(
                {
                    f'{r.get("resourceType")}/{r.get("id")}': r
                    for r in self._resources
                    if r.get("resourceType") and r.get("id")
                }.values()
            )
            null_id_resources: List[Dict[str, Any]] = [
                r for r in self._resources if not r.get("id")
            ]
            unique_resources.extend(null_id_resources)
            self._resources = unique_resources
        except Exception as e:
            raise Exception(f"Could not get parse json from: {self._resources}") from e

    @classmethod
    @override
    def from_response(cls, other_response: "FhirGetResponse") -> "FhirGetResponse":
        response: FhirGetListResponse = FhirGetListResponse(
            request_id=other_response.request_id,
            url=other_response.url,
            responses=other_response.get_response_text(),
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
        response._resources = other_response.get_resources()
        return response

    @override
    def get_response_text(self) -> str:
        """
        Gets the response text from the response

        :return: response text
        """
        return json.dumps([r for r in self._resources]) if self._resources else "[]"
