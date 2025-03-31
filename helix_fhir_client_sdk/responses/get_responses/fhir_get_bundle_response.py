from datetime import datetime
from typing import (
    Optional,
    Dict,
    Any,
    List,
    Union,
    cast,
    override,
    Tuple,
    AsyncGenerator,
)

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
from helix_fhir_client_sdk.utilities.retryable_aiohttp_url_result import (
    RetryableAioHttpUrlResult,
)


class FhirGetBundleResponse(FhirGetResponse):
    """
    This class represents a response from a FHIR server.
    NOTE: This class does converted to a Row in Spark so keep all the property types simple python types


    """

    __slots__ = FhirGetResponse.__slots__ + [
        # Specific to this subclass
        "_bundle_entries",
        "_bundle_metadata",
        "_length",
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
        bundle_entries: List[BundleEntry]
        bundle: Bundle
        bundle_entries, bundle = self._parse_bundle_entries(
            responses=response_text,
            url=url,
            status=status,
            last_modified=self.lastModified,
            etag=self.etag,
            storage_mode=self.storage_mode,
        )
        bundle_entries = FhirBundleAppender.add_operation_outcomes_to_bundle_entries(
            bundle_entries=bundle_entries,
            error=error,
            url=url,
            resource_type=resource_type,
            id_=id_,
            status=status,
            access_token=access_token,
            extra_context_to_return=extra_context_to_return,
            request_id=request_id,
            last_modified=self.lastModified,
            etag=self.etag,
            storage_mode=self.storage_mode,
        )
        self._bundle_entries: List[BundleEntry] = bundle_entries
        self._bundle_metadata: Bundle = bundle
        self._length: int = len(bundle_entries)

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

        self._length = len(self._bundle_entries)
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

        self._length = len(self._bundle_entries)
        return self

    @override
    def get_resources(self) -> List[FhirResource]:
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
        storage_mode: CompressedDictStorageMode,
    ) -> Tuple[List[BundleEntry], Bundle]:
        """
        Gets the Bundle entries from the response


        :return: list of bundle entries and a bundle with metadata but without any entries
        """
        try:
            # This is either a list of resources or a Bundle resource containing a list of resources
            child_response_resources: Union[Dict[str, Any], List[Dict[str, Any]]] = (
                cls.parse_json(responses)
            )
            assert isinstance(child_response_resources, dict)

            timestamp: Optional[str] = cast(
                Optional[str], child_response_resources.get("timestamp")
            )
            bundle: Bundle = Bundle(
                id_=child_response_resources.get("id"),
                timestamp=timestamp,
                type_=child_response_resources.get("type")
                or "collection",  # default to collection if type is not provided
                total=child_response_resources.get("total"),
            )

            # use these if the bundle entry does not have them
            request: BundleEntryRequest = BundleEntryRequest(url=url)
            response: BundleEntryResponse = BundleEntryResponse(
                status=str(status),
                lastModified=last_modified,
                etag=etag,
            )

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
                        storage_mode=storage_mode,
                    )
                    for entry in bundle_entries
                ], bundle
            else:
                return [
                    BundleEntry(
                        resource=child_response_resources,
                        request=request,
                        response=response,
                        fullUrl=None,
                        storage_mode=storage_mode,
                    )
                ], bundle
        except Exception as e:
            raise Exception(f"Could not get bundle entries from: {responses}") from e

    def create_bundle(self) -> Bundle:
        bundle_entries: List[BundleEntry] = self.get_bundle_entries()
        return Bundle(
            entry=bundle_entries,
            total=len(bundle_entries),
            id_=self._bundle_metadata.id_,
            timestamp=self._bundle_metadata.timestamp,
            type_=self._bundle_metadata.type_,
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
            self._length = len(self._bundle_entries)
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

        # convert the resources from the other response into a bundle
        bundle: Bundle = Bundle(
            # create a new bundle with the entries from the other response
            entry=other_response.get_bundle_entries(),  # this will be a list of resources from the other response
            type_="collection",  # default to collection if type is not provided
        )

        response: FhirGetBundleResponse = FhirGetBundleResponse(
            request_id=other_response.request_id,
            url=other_response.url,
            response_text=bundle.to_json(),
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
        response._bundle_entries = other_response.get_bundle_entries()
        return response

    @override
    def get_response_text(self) -> str:
        """
        Gets the response text from the response

        :return: response text
        """
        bundle: Bundle = self.create_bundle()
        return bundle.to_json()

    @override
    def sort_resources(self) -> "FhirGetBundleResponse":
        bundle: Bundle = self.create_bundle()
        bundle = FhirBundleAppender.sort_resources(bundle=bundle)
        self._bundle_entries = bundle.entry or []
        return self

    @override
    async def get_resources_generator(self) -> AsyncGenerator[FhirResource, None]:
        for entry in [e for e in self.get_bundle_entries() if e.resource]:
            yield cast(FhirResource, entry.resource)

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
            _resources=[r.to_dict() for r in self.get_resources()],
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
