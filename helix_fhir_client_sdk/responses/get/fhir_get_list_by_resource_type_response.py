import json
from collections.abc import AsyncGenerator, Generator
from logging import Logger
from typing import (
    Any,
    override,
)

from compressedfhir.fhir.fhir_bundle_entry import (
    FhirBundleEntry,
)
from compressedfhir.fhir.fhir_bundle_entry_list import FhirBundleEntryList
from compressedfhir.fhir.fhir_resource import FhirResource
from compressedfhir.fhir.fhir_resource_list import FhirResourceList
from compressedfhir.fhir.fhir_resource_map import FhirResourceMap
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from compressedfhir.utilities.fhir_json_encoder import FhirJSONEncoder

from helix_fhir_client_sdk.exceptions.fhir_get_exception import FhirGetException
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.utilities.cache.request_cache import RequestCache
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
    ]

    def __init__(
        self,
        *,
        request_id: str | None,
        url: str,
        resources: FhirResourceList,
        error: str | None,
        access_token: str | None,
        total_count: int | None,
        status: int,
        next_url: str | None = None,
        extra_context_to_return: dict[str, Any] | None,
        resource_type: str | None,
        id_: list[str] | str | None,
        response_headers: list[str] | None,  # header name and value separated by a colon
        chunk_number: int | None = None,
        cache_hits: int | None = None,
        results_by_url: list[RetryableAioHttpUrlResult],
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
        resource_map: FhirResourceMap
        count, resource_map = self._parse_into_resource_map(resources=resources)
        self._resource_map: FhirResourceMap = resource_map

    @override
    def _append(self, other_response: "FhirGetResponse") -> "FhirGetResponse":
        """
        Append the responses from other to self

        :param other_response: FhirGetResponse object to append to current one
        :return: self
        """

        new_count: int = 0

        resource_type: str | None
        if other_response.has_resource_map:
            resource_map: FhirResourceMap = other_response.get_resource_map()
            resource_list: FhirResourceList
            for resource_type, resource_list in resource_map.items():
                if resource_type not in self._resource_map:
                    self._resource_map[resource_type] = FhirResourceList()
                for resource in resource_list:
                    self._resource_map[resource_type].append(resource)
                    new_count += 1
        else:
            resources: FhirResourceList = other_response.get_resources()
            for resource in resources:
                resource_type = resource.resource_type
                if resource_type:
                    if resource_type not in self._resource_map:
                        self._resource_map[resource_type] = FhirResourceList()
                    self._resource_map[resource_type].append(resource)
                    new_count += 1

        return self

    @override
    def _extend(self, others: list["FhirGetResponse"]) -> "FhirGetResponse":
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
        raise NotImplementedError(
            self.get_resources.__name__
            + " is not implemented for "
            + self.__class__.__name__
            + ". Use "
            + self.get_resource_map.__name__
            + " instead."
        )

    @override
    def get_resource_map(self) -> FhirResourceMap:
        """
        Gets the resources from the response


        :return: list of resources
        """
        return self._resource_map

    @override
    def get_bundle_entries(self) -> FhirBundleEntryList:
        raise NotImplementedError(
            self.get_bundle_entries.__name__
            + " is not implemented for "
            + self.__class__.__name__
            + ". Use "
            + self.get_resources.__name__
            + " instead."
        )

    @classmethod
    def _parse_resources(cls, *, responses: str) -> list[dict[str, Any]]:
        """
        Gets the resources from the response


        :return: list of resources
        """
        try:
            # THis is either a list of resources or a Bundle resource containing a list of resources
            child_response_resources: dict[str, Any] | list[dict[str, Any]] = cls.parse_json(responses)
            assert isinstance(child_response_resources, list)
            return child_response_resources
        except Exception as e:
            raise FhirGetException(
                exception=e,
                message="Error parsing response: " + responses + ": " + str(e) + " - this is not a valid FHIR response",
                request_id=None,
                url=None,
                json_data=responses,
                response_text=responses,
                response_status_code=None,
                headers=None,
                variables={
                    "responses": responses,
                    "error": str(e),
                },
            ) from e

    @override
    def remove_duplicates(self) -> FhirGetResponse:
        """
        removes duplicate resources from the response i.e., resources with same resourceType and id

        """
        for _, resource_list in self._resource_map.items():
            resource_list.remove_duplicates()
        return self

    @override
    async def remove_entries_in_cache_async(
        self, *, request_cache: RequestCache, compare_hash: bool = True, logger: Logger | None
    ) -> "FhirGetResponse":
        """
        Removes the entries in the cache

        :param request_cache: The cache to remove the entries from
        :return: self
        """
        async for cached_entry in request_cache.get_entries_async():
            if cached_entry.from_input_cache:
                for _, resource_list in self._resource_map.items():
                    for resource in resource_list:
                        if (
                            resource
                            and resource.id is not None
                            and resource.id == cached_entry.id_
                            and resource.resource_type == cached_entry.resource_type
                        ):
                            if logger:
                                logger.debug(
                                    f"Removing entry from bundle with id {resource.id} and resource "
                                    f"type {resource.resource_type}"
                                )
                            resource_list.remove(resource)
                            break

        # remove any empty resource lists
        for resource_type, resources in list(self._resource_map.items()):
            if not resources:
                del self._resource_map[resource_type]
        return self

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
        return json.dumps(self._resource_map.dict(), cls=FhirJSONEncoder)

    @classmethod
    def _parse_into_resource_map(cls, resources: FhirResourceList) -> tuple[int, FhirResourceMap]:
        if isinstance(resources, FhirResourceMap):
            return resources.get_resource_count(), resources

        resource_map: FhirResourceMap = FhirResourceMap()
        resource: FhirResource
        count: int = 0
        for resource in resources:
            if resource:
                resource_type = resource.resource_type
                assert resource_type, f"No resourceType in {json.dumps(resource)}"
                if resource_type not in resource_map:
                    resource_map[resource_type] = FhirResourceList()

                count += 1
                resource_map[resource_type].append(resource)
        return count, resource_map

    @override
    def sort_resources(self) -> "FhirGetListByResourceTypeResponse":
        return self

    @override
    async def consume_resource_async(
        self,
    ) -> AsyncGenerator[FhirResource, None]:
        raise NotImplementedError(
            self.consume_resource_async.__name__
            + " is not implemented for "
            + self.__class__.__name__
            + ". Use "
            + self.consume_resource_map_async.__name__
            + " instead."
        )
        # This is here to keep the linter happy
        # noinspection PyUnreachableCode,PyTypeChecker
        yield None

    @override
    def consume_resource(self) -> Generator[FhirResource, None, None]:
        raise NotImplementedError(
            self.consume_resource.__name__
            + " is not implemented for "
            + self.__class__.__name__
            + ". Use "
            + self.consume_resource_map.__name__
            + " instead."
        )
        # This is here to keep the linter happy
        # noinspection PyUnreachableCode,PyTypeChecker
        yield None

    @override
    async def consume_resource_map_async(
        self,
    ) -> AsyncGenerator[FhirResourceMap, None]:
        yield self._resource_map
        self._resource_map = FhirResourceMap()

    @override
    def consume_resource_map(self) -> Generator[FhirResourceMap, None, None]:
        yield self._resource_map
        self._resource_map = FhirResourceMap()

    @override
    async def consume_bundle_entry_async(self) -> AsyncGenerator[FhirBundleEntry, None]:
        raise NotImplementedError(
            "get_bundle_entries_generator is not implemented for FhirGetListByResourceTypeResponse."
        )
        # noinspection PyUnreachableCode,PyTypeChecker
        yield None

    @override
    def consume_bundle_entry(self) -> Generator[FhirBundleEntry, None, None]:
        raise NotImplementedError(
            "get_bundle_entries_generator is not implemented for FhirGetListByResourceTypeResponse."
        )
        # noinspection PyUnreachableCode,PyTypeChecker
        yield None

    @override
    def to_dict(self) -> dict[str, Any]:
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
        return self._resource_map.get_resource_count()

    @override
    @property
    def has_resource_map(self) -> bool:
        return True
