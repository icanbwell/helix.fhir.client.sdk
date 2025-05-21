import json
from abc import abstractmethod
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from logging import Logger
from typing import Any, Optional, cast

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
from dateutil import parser

from helix_fhir_client_sdk.utilities.cache.request_cache import RequestCache
from helix_fhir_client_sdk.utilities.retryable_aiohttp_url_result import (
    RetryableAioHttpUrlResult,
)


class FhirGetResponse:
    """
    This class represents the response from a FHIR server for a GET request.
    It encapsulates the response data, including the status code, headers, and any errors that occurred.
    It also provides methods for processing the response, such as getting resources, handling pagination, and managing errors.
    The class is designed to be extended by specific implementations that handle different types of FHIR responses.


    """

    __slots__ = [
        "id_",
        "resource_type",
        "request_id",
        "url",
        "error",
        "access_token",
        "total_count",
        "status",
        "next_url",
        "extra_context_to_return",
        "successful",
        "response_headers",
        "chunk_number",
        "cache_hits",
        "results_by_url",
        "storage_mode",
    ]

    def __init__(
        self,
        *,
        request_id: str | None,
        url: str,
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
        """
        Class that encapsulates the response from FHIR server
        NOTE: This class does converted to a Row in Spark so keep all the property types simple python types

        :param request_id: request id
        :param resource_type: (Optional)
        :param id_: (Optional)
        :param url: url that was being accessed
        :param error: Any error returned by FHIR server
        :param access_token: access token that was used
        :param total_count: count of total records that match the provided query.
                            Only set if include_total_count was set to avoid expensive operation by server.
        :param extra_context_to_return: a dict to return with every row (separate_bundle_resources is set)
                                        or with FhirGetResponse
        :param status: status code
        :param next_url: next url to use for pagination
        :param response_headers: headers returned by the server (can have duplicate header names)
        :param chunk_number: chunk number for streaming
        :param cache_hits: count of cache hits
        :param results_by_url: results by url
        :return: None
        """
        self.id_: list[str] | str | None = id_
        self.resource_type: str | None = resource_type
        self.request_id: str | None = request_id
        self.url: str = url
        self.error: str | None = error
        """ Any error returned by the fhir server """
        self.access_token: str | None = access_token
        """ Access token used to make the request to the fhir server """
        self.total_count: int | None = total_count
        """ Total count of resources returned by the fhir serer """
        self.status: int = status
        """ Status code returned by the fhir server """ ""
        self.next_url: str | None = next_url
        """ Next url to use for pagination """
        self.extra_context_to_return: dict[str, Any] | None = extra_context_to_return
        """ Extra context to return with every row (separate_bundle_resources is set) or with FhirGetResponse"""
        self.successful: bool = status == 200
        """ True if the request was successful """
        self.response_headers: list[str] | None = response_headers
        """ Headers returned by the server (can have duplicate header names) """ ""
        self.chunk_number: int | None = chunk_number
        """ Chunk number for streaming """
        self.cache_hits: int | None = cache_hits
        """ Count of cache hits """
        self.results_by_url: list[RetryableAioHttpUrlResult] = results_by_url
        """ Count of errors in the response by status """
        self.storage_mode: CompressedDictStorageMode = storage_mode
        """ Storage mode for the response """

    @abstractmethod
    def _append(self, other_response: "FhirGetResponse") -> "FhirGetResponse": ...

    def append(self, other_response: "FhirGetResponse") -> "FhirGetResponse":
        """
        Append the responses from other to self

        :param other_response: FhirGetResponse object to append to current one
        :return: self
        """

        result: FhirGetResponse = self._append(other_response=other_response)

        if other_response.chunk_number and (other_response.chunk_number or 0) > (result.chunk_number or 0):
            result.chunk_number = other_response.chunk_number
        if other_response.next_url:
            result.next_url = other_response.next_url
            result.access_token = other_response.access_token
        result.cache_hits = (result.cache_hits or 0) + (other_response.cache_hits or 0)

        if other_response.results_by_url:
            if result.results_by_url is None:
                result.results_by_url = other_response.results_by_url
            else:
                result.results_by_url.extend(
                    [u for u in other_response.results_by_url if u not in result.results_by_url]
                )

        if other_response.access_token:
            result.access_token = other_response.access_token

        if other_response.request_id:
            result.request_id = other_response.request_id

        return result

    @abstractmethod
    def _extend(self, others: list["FhirGetResponse"]) -> "FhirGetResponse": ...

    def extend(self, others: list["FhirGetResponse"]) -> "FhirGetResponse":
        """
        Append the responses from other to self

        :param others: list of FhirGetResponse objects
        :return: self
        """
        result: FhirGetResponse = self._extend(others=others)

        latest_chunk_number: list[int] = sorted([o.chunk_number for o in others if o.chunk_number], reverse=True)
        if len(latest_chunk_number) > 0:
            result.chunk_number = latest_chunk_number[0]
        return result

    @abstractmethod
    def get_resources(self) -> FhirResourceList:
        """
        Gets the resources from the response


        :return: list of resources
        """
        ...

    @abstractmethod
    def get_resource_map(self) -> FhirResourceMap:
        """
        Gets the resources from the response as a map


        :return: map of resourceType, list of resources
        """
        ...

    @abstractmethod
    def consume_resource(self) -> Generator[FhirResource, None, None]:
        """
        Gets the resources from the response as a generator AND removes them from the response


        :return: generator of resources
        """
        # This is just here for Python lint to be happy
        yield None  # type: ignore[misc]

    @abstractmethod
    async def consume_resource_async(
        self,
    ) -> AsyncGenerator[FhirResource, None]:
        """
        Gets the resources from the response as a generator AND removes them from the response


        :return: generator of resources
        """
        # This is just here for Python lint to be happy
        yield None  # type: ignore[misc]

    async def consume_resource_map_async(
        self,
    ) -> AsyncGenerator[FhirResourceMap, None]:
        raise NotImplementedError(
            f"{self.consume_resource_map_async.__name__} is not implemented in {self.__class__.__name__}. Use {self.consume_resource_async.__name__} instead."
        )
        # This is just here for Python lint to be happy
        # noinspection PyUnreachableCode,PyTypeChecker
        yield None

    def consume_resource_map(self) -> Generator[FhirResourceMap, None, None]:
        raise NotImplementedError(
            f"{self.consume_resource_map.__name__} is not implemented in {self.__class__.__name__}. Use {self.consume_resource.__name__} instead."
        )
        # This is just here for Python lint to be happy
        # noinspection PyUnreachableCode,PyTypeChecker
        yield None

    @abstractmethod
    async def consume_bundle_entry_async(self) -> AsyncGenerator[FhirBundleEntry, None]:
        """
        Gets the resources from the response as a generator AND removes them from the response


        :return: generator of resources
        """
        # This is just here for Python lint to be happy
        yield None  # type: ignore[misc]

    @abstractmethod
    def consume_bundle_entry(self) -> Generator[FhirBundleEntry, None, None]:
        """
        Gets the resources from the response as a generator AND removes them from the response


        :return: generator of resources
        """
        # This is just here for Python lint to be happy
        yield None  # type: ignore[misc]

    @abstractmethod
    def get_bundle_entries(self) -> FhirBundleEntryList:
        """
        Gets the Bundle entries from the response


        :return: list of bundle entries
        """
        ...

    @staticmethod
    def parse_json(responses: str) -> dict[str, Any] | list[dict[str, Any]]:
        """
        Parses the json response from the fhir server


        :param responses: response from the fhir server
        :return: one of:
        1. response_resources is a list of resources
        2. response_resources is a bundle with a list of resources
        3. response_resources is a single resource
        """
        if responses is None or len(responses) == 0:
            return {
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "error",
                        "code": "exception",
                        "diagnostics": "Content was empty",
                    }
                ],
            }

        try:
            return cast(dict[str, Any] | list[dict[str, Any]], json.loads(responses))
        except json.decoder.JSONDecodeError as e:
            return {
                "resourceType": "OperationOutcome",
                "issue": [{"severity": "error", "code": "exception", "diagnostics": str(e)}],
            }

    def __repr__(self) -> str:
        instance_variables_text = json.dumps(self.to_dict())
        return f"FhirGetResponse: {instance_variables_text}"

    # noinspection PyPep8Naming
    @property
    def lastModified(self) -> datetime | None:
        """
        Returns the last modified date from the response headers

        :return: last modified date
        """
        if self.response_headers is None:
            return None
        header: str
        for header in self.response_headers:
            header_name: str = header.split(":")[0].strip()
            header_value: str = header.split(":")[1].strip()
            if header_name == "Last-Modified":
                last_modified_str: str | None = header_value
                if last_modified_str is None:
                    return None
                if isinstance(last_modified_str, datetime):
                    return last_modified_str

                try:
                    last_modified_datetime: datetime = parser.parse(last_modified_str)
                    if last_modified_datetime.tzinfo is None:
                        last_modified_datetime = last_modified_datetime.replace(tzinfo=UTC)
                    return last_modified_datetime
                except ValueError:
                    return None
        return None

    @property
    def etag(self) -> str | None:
        """
        Returns the etag from the response headers

        :return: etag
        """
        if self.response_headers is None:
            return None
        header: str
        for header in self.response_headers:
            if ":" not in header:
                continue
            header_name: str = header.split(":")[0].strip()
            header_value: str = header.split(":")[1].strip()
            if header_name == "ETag":
                return header_value
        return None

    @abstractmethod
    def remove_duplicates(self) -> "FhirGetResponse":
        """
        removes duplicate resources from the response i.e., resources with same resourceType and id

        """
        ...

    @abstractmethod
    async def remove_entries_in_cache_async(
        self, *, request_cache: RequestCache, compare_hash: bool = True, logger: Logger | None
    ) -> "FhirGetResponse":
        """
        removes entries in the cache for the given response

        :param request_cache: cache to remove entries from
        :param compare_hash: whether to compare hash or not
        :return: FhirGetResponse
        """
        ...

    def get_resource_type_and_ids(self) -> list[str]:
        """
        Gets the ids of the resources from the response
        """
        resources: FhirResourceList = self.get_resources()
        try:
            return resources.get_resource_type_and_ids()
        except Exception as e:
            raise Exception(f"Could not get resourceType and id from resources: {resources.json()}") from e

    @classmethod
    async def from_async_generator(
        cls, generator: AsyncGenerator["FhirGetResponse", None]
    ) -> Optional["FhirGetResponse"]:
        """
        Reads a generator of FhirGetResponse and returns a single FhirGetResponse by appending all the FhirGetResponse

        :param generator: generator of FhirGetResponse items
        :return: FhirGetResponse
        """
        result: FhirGetResponse | None = None
        async for value in generator:
            if not result:
                result = value
            else:
                result = result.append(value)

        assert result
        return result

    def get_operation_outcomes(self) -> FhirResourceList:
        """
        Gets the operation outcomes from the response

        :return: list of operation outcomes
        """
        return self.get_resources().get_operation_outcomes()

    def get_resources_except_operation_outcomes(self) -> FhirResourceList:
        """
        Gets the normal FHIR resources by skipping any OperationOutcome resources

        :return: list of valid resources
        """
        return self.get_resources().get_resources_except_operation_outcomes()

    def to_dict(self) -> dict[str, Any]:
        """
        Converts the object to a dictionary

        :return: dictionary
        """
        return {
            "id_": self.id_,
            "resource_type": self.resource_type,
            "request_id": self.request_id,
            "url": self.url,
            "error": self.error,
            "access_token": self.access_token,
            "total_count": self.total_count,
            "status": self.status,
            "next_url": self.next_url,
            "extra_context_to_return": self.extra_context_to_return,
            "successful": self.successful,
            "response_headers": self.response_headers,
            "chunk_number": self.chunk_number,
            "cache_hits": self.cache_hits,
            "results_by_url": [r.to_dict() for r in self.results_by_url],
            "storage_type": self.storage_mode.storage_type,
            "last_modified": self.lastModified,
        }

    @classmethod
    @abstractmethod
    def from_response(cls, other_response: "FhirGetResponse") -> "FhirGetResponse":
        """
        Creates a new instance of the class from another response class
        """
        ...

    @abstractmethod
    def get_response_text(self) -> str:
        """
        Gets the response text from the FHIR server

        :return: response text
        """
        """
        :return: string representation of the response
        """
        raise NotImplementedError(
            "Subclasses must implement the get_response_text method to return the response text from the FHIR server"
        )

    @abstractmethod
    def sort_resources(self) -> "FhirGetResponse": ...

    @abstractmethod
    def get_resource_count(self) -> int:
        """
        Get the count of resources in the response

        Returns:
            Count of resources
        """
        ...

    @property
    def has_resource_map(self) -> bool:
        """
        Returns True if the response has a resource map

        :return: True if the response has a resource map
        """
        return False

    @property
    def has_single_resource(self) -> bool:
        """
        Returns True if the response has a single resource

        :return: True if the response has a single resource
        """
        return False
