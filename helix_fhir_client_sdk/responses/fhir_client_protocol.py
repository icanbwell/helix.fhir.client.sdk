import uuid
from datetime import datetime
from threading import Lock
from typing import Protocol, Optional, Dict, Any, Tuple, List, Union, AsyncGenerator
from aiohttp import ClientSession, ClientResponse
from requests.adapters import BaseAdapter

from helix_fhir_client_sdk.filters.base_filter import BaseFilter
from helix_fhir_client_sdk.filters.sort_field import SortField
from helix_fhir_client_sdk.function_types import (
    RefreshTokenFunction,
    HandleStreamingChunkFunction,
    HandleStreamingResourcesFunction,
)
from helix_fhir_client_sdk.loggers.fhir_logger import FhirLogger
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


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
    _adapter: Optional[BaseAdapter]
    _limit: Optional[int]
    _validation_server_url: Optional[str]
    _separate_bundle_resources: bool
    _obj_id: Optional[str]
    _include_total: bool
    _filters: List[BaseFilter]
    _expand_fhir_bundle: bool

    _stop_processing: bool = False
    _authentication_token_lock: Lock
    _last_page: Optional[int]

    _use_data_streaming: bool = False
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

    async def get_access_token_async(self) -> Optional[str]: ...

    async def _send_fhir_request_async(
        self,
        *,
        http: ClientSession,
        full_url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any] | None,
    ) -> ClientResponse: ...

    async def _expand_bundle_async(
        self,
        resources: str,
        response_json: Dict[str, Any],
        total_count: int,
        access_token: Optional[str],
        url: str,
    ) -> Tuple[str, int]: ...

    async def get_safe_response_text_async(
        self, response: Optional[ClientResponse]
    ) -> str: ...

    def create_http_session(self) -> ClientSession: ...

    async def _get_with_session_async(
        self,
        *,
        session: Optional[ClientSession],
        page_number: Optional[int],
        ids: Optional[List[str]],
        id_above: Optional[str],
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction],
        additional_parameters: Optional[List[str]],
        fn_resource_chunk_handler: Optional[HandleStreamingResourcesFunction],
    ) -> AsyncGenerator[FhirGetResponse, None]: ...

    def separate_bundle_resources(self, separate_bundle_resources: bool):  # type: ignore[no-untyped-def]
        ...

    def resource(self, resource: str):  # type: ignore[no-untyped-def]
        ...

    def set_access_token(self, value: str) -> Any: ...
