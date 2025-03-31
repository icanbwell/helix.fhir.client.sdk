import json
from typing import Optional, Dict, Any, List, Union, override, AsyncGenerator

from helix_fhir_client_sdk.fhir.bundle import Bundle
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


class FhirGetErrorResponse(FhirGetResponse):
    """
    This class represents a response from a FHIR server.
    NOTE: This class does converted to a Row in Spark so keep all the property types simple python types


    """

    __slots__ = FhirGetResponse.__slots__ + [
        # Specific to this subclass
        "_error_text",
        "_resource",
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
        self._error_text: Optional[str] = response_text
        self._resource: Optional[FhirResource] = self._parse_response_text(
            response_text=response_text,
            error=error,
            url=url,
            resource_type=resource_type,
            id_=id_,
            status=status,
            access_token=access_token,
            extra_context_to_return=extra_context_to_return,
            request_id=request_id,
            storage_mode=storage_mode,
        )

    @override
    def _append(self, other_response: "FhirGetResponse") -> "FhirGetResponse":
        """
        Append the responses from other to self

        :param other_response: FhirGetResponse object to append to current one
        :return: self
        """
        # if someone is trying to append to a single resource then we need to convert it to a bundle
        raise NotImplementedError(
            "FhirGetErrorResponse does not support appending other responses."
        )

    @override
    def _extend(self, others: List["FhirGetResponse"]) -> "FhirGetResponse":
        """
        Append the responses from other to self

        :param others: list of FhirGetResponse objects
        :return: self
        """
        # if someone is trying to append to a single resource then we need to convert it to a bundle
        raise NotImplementedError(
            "FhirGetErrorResponse does not support extending with other responses."
        )

    @override
    def get_resources(self) -> List[FhirResource]:
        """
        Gets the resources from the response


        :return: list of resources
        """
        return [self._resource] if self._resource else []

    @override
    def get_bundle_entries(self) -> List[BundleEntry]:
        """
        Gets the Bundle entries from the response


        :return: list of bundle entries
        """
        return (
            [
                BundleEntry(
                    resource=self._resource,  # This will be the OperationOutcome or the resource itself
                    request=BundleEntryRequest(url=self.url),
                    response=BundleEntryResponse(
                        status=str(self.status),
                        lastModified=self.lastModified,
                        etag=self.etag,
                    ),
                    storage_mode=self.storage_mode,
                )
            ]
            if self._resource
            else []
        )

    @override
    def remove_duplicates(self) -> FhirGetResponse:
        """
        removes duplicate resources from the response i.e., resources with same resourceType and id

        """
        return self  # nothing to do since this is a single resource

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
        return (
            json.dumps(self._resource.to_dict(), cls=FhirJSONEncoder)
            if self._resource
            else ""
        )

    @classmethod
    def _parse_response_text(
        cls,
        *,
        response_text: Optional[str],
        error: Optional[str],
        url: str,
        resource_type: Optional[str],
        id_: Optional[str | List[str]],
        status: int,
        access_token: Optional[str],
        extra_context_to_return: Optional[Dict[str, Any]],
        request_id: Optional[str],
        storage_mode: CompressedDictStorageMode,
    ) -> Optional[FhirResource]:
        """
        Parses the response text to extract any useful information. This can be overridden by subclasses.

        :return: parsed response text or None if not applicable
        """
        response_json: Dict[str, Any] | None = None
        if response_text:
            # we don't know if the response text is FHIR resource or not
            # noinspection PyBroadException
            try:
                # check if the response is a valid json
                # if it is not then we will just return the response text as it is
                json.loads(response_text)
            except Exception:
                # No resource was found in the response
                return None

            child_response_resources: Dict[str, Any] | List[Dict[str, Any]] = (
                cls.parse_json(response_text)
            )
            assert isinstance(child_response_resources, dict)
            response_json = child_response_resources
            return Bundle.add_diagnostics_to_operation_outcomes(
                resource=FhirResource(
                    initial_dict=response_json, storage_mode=storage_mode
                ),
                diagnostics_coding=FhirBundleAppender.get_diagnostic_coding(
                    access_token=access_token,
                    url=url,
                    resource_type=resource_type,
                    id_=id_,
                    status=status,
                ),
            )
        elif error:
            # create an operation outcome resource
            return FhirBundleAppender.create_operation_outcome_resource(
                error=error,
                url=url,
                resource_type=resource_type,
                id_=id_,
                status=status,
                access_token=access_token,
                extra_context_to_return=extra_context_to_return,
                request_id=request_id,
                storage_mode=storage_mode,
            )

        return FhirResource(initial_dict=response_json, storage_mode=storage_mode)

    @override
    def sort_resources(self) -> "FhirGetErrorResponse":
        return self

    @override
    async def get_resources_generator(self) -> AsyncGenerator[FhirResource, None]:
        for resource in self.get_resources():
            yield resource

    @override
    async def get_bundle_entries_generator(self) -> AsyncGenerator[BundleEntry, None]:
        for entry in self.get_bundle_entries():
            yield entry

    @override
    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the object to a dictionary

        :return: dictionary
        """
        return dict(
            request_id=self.request_id,
            url=self.url,
            _resource=self._resource.to_dict() if self._resource else None,
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
