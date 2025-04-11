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
    Generator,
    Set,
)

from compressedfhir.fhir.fhir_bundle import FhirBundle
from compressedfhir.fhir.fhir_bundle_entry import FhirBundleEntry
from compressedfhir.fhir.fhir_bundle_entry_request import FhirBundleEntryRequest
from compressedfhir.fhir.fhir_bundle_entry_response import (
    FhirBundleEntryResponse,
)
from compressedfhir.fhir.fhir_bundle_entry_list import FhirBundleEntryList
from compressedfhir.fhir.fhir_resource_list import FhirResourceList
from compressedfhir.fhir.fhir_resource_map import FhirResourceMap
from helix_fhir_client_sdk.fhir_bundle_appender import FhirBundleAppender
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from compressedfhir.fhir.fhir_resource import FhirResource
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
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
        bundle_entries: FhirBundleEntryList
        bundle: FhirBundle
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
        self._bundle_entries: FhirBundleEntryList = bundle_entries
        self._bundle_metadata: FhirBundle = bundle

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
    def get_resources(self) -> FhirResourceList:
        """
        Gets the resources from the response


        :return: list of resources
        """

        return FhirResourceList(
            c.resource for c in self._bundle_entries if c.resource is not None
        )

    @override
    def get_resource_map(self) -> FhirResourceMap:
        """
        Gets the resources from the response as a map


        :return: map of resourceType, list of resources
        """
        raise NotImplementedError(
            self.get_resource_map.__name__
            + " is not implemented for "
            + self.__class__.__name__
            + ". Use "
            + self.get_resources.__name__
            + " instead."
        )

    @override
    def get_bundle_entries(self) -> FhirBundleEntryList:
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
    ) -> Tuple[FhirBundleEntryList, FhirBundle]:
        """
        Gets the Bundle entries from the response


        :return: list of bundle entries and a bundle with metadata but without any entries
        """
        assert isinstance(
            storage_mode, CompressedDictStorageMode
        ), f"Expected CompressedDictStorageMode but got {type(storage_mode)}"

        if not responses:
            return FhirBundleEntryList(), FhirBundle(
                id_=None,
                timestamp=None,
                type_="collection",
            )
        try:
            # This is either a list of resources or a Bundle resource containing a list of resources
            child_response_resources: Union[Dict[str, Any], List[Dict[str, Any]]] = (
                cls.parse_json(responses)
            )
            assert isinstance(child_response_resources, dict)

            timestamp: Optional[str] = cast(
                Optional[str], child_response_resources.get("timestamp")
            )
            bundle: FhirBundle = FhirBundle(
                id_=child_response_resources.get("id"),
                timestamp=timestamp,
                type_=child_response_resources.get("type")
                or "collection",  # default to collection if type is not provided
                total=child_response_resources.get("total"),
            )

            # use these if the bundle entry does not have them
            request: FhirBundleEntryRequest = FhirBundleEntryRequest(url=url)
            response: FhirBundleEntryResponse = FhirBundleEntryResponse(
                status=str(status),
                lastModified=last_modified,
                etag=etag,
            )

            result: FhirBundleEntryList = FhirBundleEntryList()

            # otherwise it is a bundle so parse out the resources
            if "entry" in child_response_resources:
                bundle_entries: List[Dict[str, Any]] = child_response_resources["entry"]
                for entry in bundle_entries:
                    result.append(
                        FhirBundleEntry(
                            resource=entry["resource"],
                            request=(
                                FhirBundleEntryRequest.from_dict(
                                    cast(Dict[str, Any], entry.get("request"))
                                )
                                if entry.get("request")
                                and isinstance(entry.get("request"), dict)
                                else request
                            ),
                            response=(
                                FhirBundleEntryResponse.from_dict(
                                    cast(Dict[str, Any], entry.get("response"))
                                )
                                if entry.get("response")
                                and isinstance(entry.get("response"), dict)
                                else response
                            ),
                            fullUrl=entry.get("fullUrl"),
                            storage_mode=storage_mode,
                        )
                    )
                return result, bundle
            else:
                result.append(
                    FhirBundleEntry(
                        resource=child_response_resources,
                        request=request,
                        response=response,
                        fullUrl=None,
                        storage_mode=storage_mode,
                    )
                )
                return result, bundle
        except Exception as e:
            raise Exception(f"Could not get bundle entries from: {responses}") from e

    def create_bundle(self) -> FhirBundle:
        bundle_entries: FhirBundleEntryList = self.get_bundle_entries()
        return FhirBundle(
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
        bundle: FhirBundle = self.create_bundle()
        try:
            # remove duplicates from the list if they have the same resourceType and id
            resource_type_plus_id_seen: Set[str] = set()
            entry_request_url_seen: Set[str] = set()
            i = 0
            while i < len(self._bundle_entries):
                if self._bundle_entries[i] is not None:
                    # Create a tuple of values for specified keys
                    resource = self._bundle_entries[i].resource
                    resource_id: Optional[str] = (
                        resource.id if resource is not None else None
                    )
                    resource_type_plus_id: Optional[str] = (
                        resource.resource_type_and_id if resource is not None else None
                    )
                    request = self._bundle_entries[i].request
                    entry_request_url: Optional[str] = (
                        request.url if request is not None else None
                    )

                    if resource_id is None and entry_request_url is not None:
                        # check only the entry request url if the resource has no id
                        if entry_request_url in entry_request_url_seen:
                            # Remove duplicate entry
                            self._bundle_entries.remove(self._bundle_entries[i])
                        else:
                            entry_request_url_seen.add(entry_request_url)
                    elif resource_type_plus_id is not None:  # resource has an id
                        if resource_type_plus_id in resource_type_plus_id_seen:
                            # Remove duplicate entry
                            self._bundle_entries.remove(self._bundle_entries[i])
                        else:
                            resource_type_plus_id_seen.add(resource_type_plus_id)
                i += 1
            return self
        except Exception as e:
            raise Exception(f"Could not get parse json from: {bundle}") from e

    @classmethod
    @override
    def from_response(
        cls, other_response: "FhirGetResponse"
    ) -> "FhirGetBundleResponse":
        """
        Creates a new FhirGetBundleResponse from another FhirGetResponse

        :param other_response: FhirGetResponse object to create a new FhirGetBundleResponse from
        :return: FhirGetBundleResponse object created from the other_response
        """
        if isinstance(other_response, FhirGetBundleResponse):
            return other_response

        # convert the resources from the other response into a bundle
        bundle: FhirBundle = FhirBundle(
            # create a new bundle with the entries from the other response
            entry=other_response.get_bundle_entries(),  # this will be a list of resources from the other response
            type_="collection",  # default to collection if type is not provided
        )

        response: FhirGetBundleResponse = FhirGetBundleResponse(
            request_id=other_response.request_id,
            url=other_response.url,
            response_text=bundle.json(),
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
        bundle: FhirBundle = self.create_bundle()
        return bundle.json()

    @override
    def sort_resources(self) -> "FhirGetBundleResponse":
        bundle: FhirBundle = self.create_bundle()
        bundle = FhirBundleAppender.sort_resources(bundle=bundle)
        self._bundle_entries = (
            FhirBundleEntryList(bundle.entry) if bundle.entry else FhirBundleEntryList()
        )
        return self

    @override
    async def consume_resource_async(
        self,
    ) -> AsyncGenerator[FhirResource, None]:
        while self._bundle_entries:
            entry: FhirBundleEntry = self._bundle_entries.popleft()
            if entry.resource:
                yield entry.resource

    @override
    def consume_resource(self) -> Generator[FhirResource, None, None]:
        while self._bundle_entries:
            entry: FhirBundleEntry = self._bundle_entries.popleft()
            if entry.resource:
                yield entry.resource

    @override
    async def consume_bundle_entry_async(self) -> AsyncGenerator[FhirBundleEntry, None]:
        while self._bundle_entries:
            yield self._bundle_entries.popleft()

    @override
    def consume_bundle_entry(self) -> Generator[FhirBundleEntry, None, None]:
        while self._bundle_entries:
            yield self._bundle_entries.popleft()

    @override
    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the object to a dictionary

        :return: dictionary
        """
        return dict(
            request_id=self.request_id,
            url=self.url,
            _resources=[r.dict() for r in self.get_resources()],
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
        return len(self._bundle_entries)

    def __repr__(self) -> str:
        return (
            f"FhirGetBundleResponse(request_id={self.request_id}"
            f", url={self.url}"
            f", count={self.get_resource_count()}"
        )
