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


class FhirSingleGetResponse(FhirGetResponse):
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
            responses=responses,
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
        self._resource: Optional[Dict[str, Any]] = self._parse_single_resource()

    @override
    def append(self, other_response: "FhirGetResponse") -> "FhirGetResponse":
        """
        Append the responses from other to self

        :param other_response: FhirGetResponse object to append to current one
        :return: self
        """
        raise NotImplementedError("FhirSingleGetResponse does not support append")

    @override
    def extend(self, others: List["FhirGetResponse"]) -> "FhirGetResponse":
        """
        Append the responses from other to self

        :param others: list of FhirGetResponse objects
        :return: self
        """
        raise NotImplementedError("FhirSingleGetResponse does not support extend")

    @override
    def get_resources(self) -> List[Dict[str, Any]]:
        """
        Gets the resources from the response


        :return: list of resources
        """
        if not self.responses:
            return []

        return [self._resource] if self._resource else []

    @override
    def get_bundle_entries(self) -> List[BundleEntry]:
        """
        Gets the Bundle entries from the response


        :return: list of bundle entries
        """
        if not self.responses:
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
                BundleEntry(resource=self._resource, request=request, response=response)
            ]
        except Exception as e:
            raise Exception(
                f"Could not get bundle entries from: {self.responses}"
            ) from e

    @override
    def remove_duplicates(self) -> None:
        """
        removes duplicate resources from the response i.e., resources with same resourceType and id

        """
        return  # nothing to do since this is a single resource

    def _parse_single_resource(self) -> Dict[str, Any]:
        """
        Gets the single resource from the response

        :return: single resource
        """
        if not self.responses:
            return {}
        try:
            # THis is either a list of resources or a Bundle resource containing a list of resources
            child_response_resources: Dict[str, Any] | List[Dict[str, Any]] = (
                self.parse_json(self.responses)
            )
            assert isinstance(child_response_resources, dict)
            return child_response_resources
        except Exception as e:
            raise Exception(f"Could not get resources from: {self.responses}") from e
