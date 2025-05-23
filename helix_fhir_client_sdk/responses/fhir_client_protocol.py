import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from logging import Logger
from threading import Lock
from typing import (
    Any,
    Protocol,
    runtime_checkable,
)

from aiohttp import ClientSession
from compressedfhir.fhir.fhir_bundle import FhirBundle
from compressedfhir.fhir.fhir_resource_list import FhirResourceList
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from requests.adapters import BaseAdapter

from helix_fhir_client_sdk.filters.base_filter import BaseFilter
from helix_fhir_client_sdk.filters.sort_field import SortField
from helix_fhir_client_sdk.function_types import (
    HandleStreamingChunkFunction,
    RefreshTokenFunction,
    TraceRequestFunction,
)
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.merge.fhir_merge_resource_response import (
    FhirMergeResourceResponse,
)
from helix_fhir_client_sdk.structures.get_access_token_result import (
    GetAccessTokenResult,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_client import (
    RetryableAioHttpClient,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_response import (
    RetryableAioHttpResponse,
)
from helix_fhir_client_sdk.well_known_configuration import (
    WellKnownConfigurationCacheEntry,
)


# noinspection PyTypeChecker
@runtime_checkable
class FhirClientProtocol(Protocol):
    """
    FhirClientProtocol defines the interface for a FHIR client.
    """

    _action: str | None
    _action_payload: dict[str, Any] | None
    _resource: str | None
    _id: list[str] | str | None
    _url: str | None
    _additional_parameters: list[str] | None
    _filter_by_resource: str | None
    _filter_parameter: str | None
    _include_only_properties: list[str] | None
    _page_number: int | None
    _page_size: int | None
    _last_updated_after: datetime | None
    _last_updated_before: datetime | None
    _sort_fields: list[SortField] | None
    _auth_server_url: str | None
    _auth_wellknown_url: str | None
    _auth_scopes: list[str] | None
    _login_token: str | None
    _client_id: str | None
    _access_token: str | None
    _access_token_expiry_date: datetime | None
    _logger: Logger | None
    _internal_logger: Logger
    _adapter: BaseAdapter | None
    _limit: int | None
    _validation_server_url: str | None
    _separate_bundle_resources: bool
    _obj_id: str | None
    _include_total: bool
    _filters: list[BaseFilter]
    _expand_fhir_bundle: bool
    _smart_merge: bool | None

    _stop_processing: bool = False
    _last_page: int | None

    _use_data_streaming: bool = False
    _send_data_as_chunked: bool = False
    _last_page_lock: Lock

    _use_post_for_search: bool = False

    _accept: str
    _content_type: str
    _additional_request_headers: dict[str, str]
    _accept_encoding: str

    _maximum_time_to_retry_on_429: int

    _extra_context_to_return: dict[str, Any] | None

    _retry_count: int
    _exclude_status_codes_from_retry: list[int] | None

    _uuid: uuid.UUID
    _log_level: str | None
    # default to built-in function to refresh token
    _refresh_token_function: RefreshTokenFunction
    _trace_request_function: TraceRequestFunction | None
    _chunk_size: int
    _time_to_live_in_secs_for_cache: int
    _well_known_configuration_cache_lock: Lock

    _well_known_configuration_cache: dict[str, WellKnownConfigurationCacheEntry]

    _compress: bool

    _throw_exception_on_error: bool

    _log_all_response_urls: bool

    _storage_mode: CompressedDictStorageMode
    """ storage mode to store the responses """

    _create_operation_outcome_for_error: bool | None
    """ whether to create OperationOutcome resource for errors """

    async def get_access_token_async(self) -> GetAccessTokenResult: ...

    async def _send_fhir_request_async(
        self,
        *,
        client: RetryableAioHttpClient,
        full_url: str,
        headers: dict[str, str],
        payload: dict[str, Any] | None,
    ) -> RetryableAioHttpResponse: ...

    def create_http_session(self) -> ClientSession: ...

    async def _get_with_session_async(
        self,
        *,
        page_number: int | None,
        ids: list[str] | None,
        id_above: str | None,
        fn_handle_streaming_chunk: HandleStreamingChunkFunction | None,
        additional_parameters: list[str] | None,
        resource_type: str | None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        # This is here to tell Python that this is an async generator
        yield None  # type: ignore[misc]

    def separate_bundle_resources(self, separate_bundle_resources: bool) -> "FhirClientProtocol": ...

    def resource(self, resource: str) -> "FhirClientProtocol": ...

    def set_access_token(self, value: str | None) -> "FhirClientProtocol": ...

    def set_access_token_expiry_date(self, value: datetime | None) -> "FhirClientProtocol": ...

    def include_only_properties(self, include_only_properties: list[str] | None) -> "FhirClientProtocol": ...

    def page_size(self, page_size: int) -> "FhirClientProtocol": ...

    def filter(self, filter_: list[BaseFilter]) -> "FhirClientProtocol": ...

    def clone(self) -> "FhirClientProtocol": ...

    def last_page(self, last_page: int) -> "FhirClientProtocol": ...

    def page_number(self, page_number: int) -> "FhirClientProtocol": ...

    def id_(self, id_: list[str] | str | None) -> "FhirClientProtocol": ...

    def additional_parameters(self, additional_parameters: list[str]) -> "FhirClientProtocol": ...

    def action_payload(self, action_payload: dict[str, Any]) -> "FhirClientProtocol": ...

    def action(self, action: str) -> "FhirClientProtocol": ...

    async def build_url(
        self,
        *,
        additional_parameters: list[str] | None,
        id_above: str | None,
        ids: list[str] | None,
        page_number: int | None,
        resource_type: str | None,
    ) -> str: ...

    def throw_exception_on_error(self, throw_exception_on_error: bool) -> "FhirClientProtocol": ...

    async def merge_resources_async(
        self,
        id_: str | None,
        resources_to_merge: FhirResourceList,
        batch_size: int | None,
    ) -> AsyncGenerator[FhirMergeResourceResponse, None]:
        # this is just here to tell Python this returns a generator
        yield None  # type: ignore[misc]

    async def merge_bundle_async(
        self,
        id_: str | None,
        bundle: FhirBundle,
    ) -> AsyncGenerator[FhirMergeResourceResponse, None]:
        # this is just here to tell Python this returns a generator
        yield None  # type: ignore[misc]
