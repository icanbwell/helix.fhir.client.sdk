import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Union, cast, override

from helix_fhir_client_sdk.fhir_bundle import (
    BundleEntry,
    BundleEntryRequest,
    BundleEntryResponse,
    Bundle,
)
from helix_fhir_client_sdk.fhir_bundle_appender import FhirBundleAppender
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder
from helix_fhir_client_sdk.utilities.retryable_aiohttp_url_result import (
    RetryableAioHttpUrlResult,
)


class FhirGetBundleResponse(FhirGetResponse):
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
        self._bundle_entries: List[BundleEntry] = self._parse_bundle_entries(
            responses=responses,
            url=url,
            status=status,
            last_modified=self.lastModified,
            etag=self.etag,
        )

    @override
    def _append(self, other_response: "FhirGetResponse") -> "FhirGetResponse":
        """
        Append the responses from other to self

        :param other_response: FhirGetResponse object to append to current one
        :return: self
        """

        if self._bundle_entries is None:
            self._bundle_entries = other_response.get_bundle_entries()
        else:
            self._bundle_entries.extend(other_response.get_bundle_entries())

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
        return self._bundle_entries

    @classmethod
    def _parse_bundle_entries(
        cls,
        *,
        responses: str,
        url: str,
        status: int,
        last_modified: Optional[datetime],
        etag: Optional[str],
    ) -> List[BundleEntry]:
        """
        Gets the Bundle entries from the response


        :return: list of bundle entries
        """
        try:
            # THis is either a list of resources or a Bundle resource containing a list of resources
            child_response_resources: Union[Dict[str, Any], List[Dict[str, Any]]] = (
                cls.parse_json(responses)
            )

            # use these if the bundle entry does not have them
            request: BundleEntryRequest = BundleEntryRequest(url=url)
            response: BundleEntryResponse = BundleEntryResponse(
                status=str(status),
                lastModified=last_modified,
                etag=etag,
            )
            # if it is a list of resources then wrap them in a bundle entry and return them
            if isinstance(child_response_resources, list):
                return [
                    BundleEntry(resource=r, request=request, response=response)
                    for r in child_response_resources
                ]
            # otherwise it is a bundle so parse out the resources
            if "entry" in child_response_resources:
                bundle_entries: List[Dict[str, Any]] = child_response_resources["entry"]
                return [
                    BundleEntry(
                        resource=entry["resource"],
                        request=(
                            BundleEntryRequest.from_dict(
                                cast(Dict[str, Any], entry.get("request"))
                            )
                            if entry.get("request")
                            and isinstance(entry.get("request"), dict)
                            else request
                        ),
                        response=(
                            BundleEntryResponse.from_dict(
                                cast(Dict[str, Any], entry.get("response"))
                            )
                            if entry.get("response")
                            and isinstance(entry.get("response"), dict)
                            else response
                        ),
                        fullUrl=entry.get("fullUrl"),
                    )
                    for entry in bundle_entries
                ]
            else:
                return [
                    BundleEntry(
                        resource=child_response_resources,
                        request=request,
                        response=response,
                    )
                ]
        except Exception as e:
            raise Exception(f"Could not get bundle entries from: {responses}") from e

    def create_bundle(self) -> Bundle:
        bundle_entries: List[BundleEntry] = self.get_bundle_entries()
        return Bundle(
            entry=bundle_entries,
            total_count=len(bundle_entries),
        )

    @override
    def remove_duplicates(self) -> "FhirGetBundleResponse":
        """
        removes duplicate resources from the response i.e., resources with same resourceType and id

        """
        bundle: Bundle = self.create_bundle()
        try:
            # remove duplicates from the bundle
            # this will remove duplicates from the bundle and return a new bundle
            # with the duplicates removed
            bundle = FhirBundleAppender.remove_duplicate_resources(bundle=bundle)
            self._bundle_entries = bundle.entry or []
            return self
        except Exception as e:
            raise Exception(f"Could not get parse json from: {bundle}") from e

    @classmethod
    @override
    def from_response(cls, other_response: "FhirGetResponse") -> "FhirGetResponse":
        """
        Creates a new FhirGetBundleResponse from another FhirGetResponse

        :param other_response: FhirGetResponse object to create a new FhirGetBundleResponse from
        :return: FhirGetBundleResponse object created from the other_response
        """
        if isinstance(other_response, FhirGetBundleResponse):
            return other_response

        response: FhirGetBundleResponse = FhirGetBundleResponse(
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
        response._bundle_entries = other_response.get_bundle_entries()
        return response

    @override
    def get_response_text(self) -> str:
        """
        Gets the response text from the response

        :return: response text
        """
        bundle: Bundle = self.create_bundle()
        return json.dumps(bundle.to_dict(), cls=FhirJSONEncoder)

    def sort_resources(self) -> "FhirGetBundleResponse":
        bundle: Bundle = self.create_bundle()
        bundle = FhirBundleAppender.sort_resources(bundle=bundle)
        self._bundle_entries = bundle.entry or []
        return self
