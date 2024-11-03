import uuid
from datetime import datetime
from logging import Logger
from threading import Lock
from typing import Protocol, Optional, Dict, Any, List, Union, AsyncGenerator

from aiohttp import ClientSession
from requests.adapters import BaseAdapter

from helix_fhir_client_sdk.filters.base_filter import BaseFilter
from helix_fhir_client_sdk.filters.sort_field import SortField
from helix_fhir_client_sdk.function_types import (
    RefreshTokenFunction,
    HandleStreamingChunkFunction,
)
from helix_fhir_client_sdk.loggers.fhir_logger import FhirLogger
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.utilities.retryable_aiohttp_client import (
    RetryableAioHttpClient,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_response import (
    RetryableAioHttpResponse,
)
from helix_fhir_client_sdk.well_known_configuration import (
    WellKnownConfigurationCacheEntry,
)


class FhirClientProtocol(Protocol):
    _action: Optional[str]
    _action_payload: Optional[Dict[str, Any]]
    _resource: Optional[str]
    _id: Optional[Union[List[str], str]]
    _url: Optional[str]
    _additional_parameters: Optional[List[str]]
    _filter_by_resource: Optional[str]
    _filter_parameter: Optional[str]
    _include_only_properties: Optional[List[str]]
    _page_number: Optional[int]
    _page_size: Optional[int]
    _last_updated_after: Optional[datetime]
    _last_updated_before: Optional[datetime]
    _sort_fields: Optional[List[SortField]]
    _auth_server_url: Optional[str]
    _auth_wellknown_url: Optional[str]
    _auth_scopes: Optional[List[str]]
    _login_token: Optional[str]
    _client_id: Optional[str]
    _access_token: Optional[str]
    _logger: Optional[FhirLogger]
    _internal_logger: Logger
    _adapter: Optional[BaseAdapter]
    _limit: Optional[int]
    _validation_server_url: Optional[str]
    _separate_bundle_resources: bool
    _obj_id: Optional[str]
    _include_total: bool
    _filters: List[BaseFilter]
    _expand_fhir_bundle: bool

    _stop_processing: bool = False
    _last_page: Optional[int]

    _use_data_streaming: bool = False
    _send_data_as_chunked: bool = False
    _last_page_lock: Lock

    _use_post_for_search: bool = False

    _accept: str
    _content_type: str
    _additional_request_headers: Dict[str, str]
    _accept_encoding: str

    _maximum_time_to_retry_on_429: int

    _extra_context_to_return: Optional[Dict[str, Any]]

    _retry_count: int
    _exclude_status_codes_from_retry: Optional[List[int]]

    _uuid: uuid.UUID
    _log_level: Optional[str]
    # default to built-in function to refresh token
    _refresh_token_function: RefreshTokenFunction
    _chunk_size: int
    _time_to_live_in_secs_for_cache: int
    _well_known_configuration_cache_lock: Lock

    _well_known_configuration_cache: Dict[str, WellKnownConfigurationCacheEntry]

    _compress: bool

    _throw_exception_on_error: bool

    async def get_access_token_async(self) -> Optional[str]: ...

    async def _send_fhir_request_async(
        self,
        *,
        client: RetryableAioHttpClient,
        full_url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any] | None,
    ) -> RetryableAioHttpResponse: ...

    def create_http_session(self) -> ClientSession: ...

    async def _get_with_session_async(
        self,
        *,
        page_number: Optional[int],
        ids: Optional[List[str]],
        id_above: Optional[str],
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction],
        additional_parameters: Optional[List[str]],
        resource_type: Optional[str],
    ) -> AsyncGenerator[FhirGetResponse, None]: ...

    def separate_bundle_resources(self, separate_bundle_resources: bool):  # type: ignore[no-untyped-def]
        ...

    def resource(self, resource: str):  # type: ignore[no-untyped-def]
        ...

    def set_access_token(self, value: str | None) -> "FhirClientProtocol": ...

    def include_only_properties(
        self, include_only_properties: List[str] | None
    ) -> "FhirClientProtocol": ...

    def page_size(self, page_size: int) -> "FhirClientProtocol": ...

    def filter(self, filter_: List[BaseFilter]) -> "FhirClientProtocol": ...

    def clone(self) -> "FhirClientProtocol": ...

    def last_page(self, last_page: int) -> "FhirClientProtocol": ...

    def page_number(self, page_number: int) -> "FhirClientProtocol": ...

    def id_(self, id_: Union[List[str], str] | None) -> "FhirClientProtocol": ...

    def additional_parameters(
        self, additional_parameters: List[str]
    ) -> "FhirClientProtocol": ...

    def action_payload(
        self, action_payload: Dict[str, Any]
    ) -> "FhirClientProtocol": ...

    def action(self, action: str) -> "FhirClientProtocol": ...

    async def build_url(
        self,
        *,
        additional_parameters: Optional[List[str]],
        id_above: Optional[str],
        ids: Optional[List[str]],
        page_number: Optional[int],
        resource_type: Optional[str],
    ) -> str: ...

    def throw_exception_on_error(
        self, throw_exception_on_error: bool
    ) -> "FhirClientProtocol": ...
