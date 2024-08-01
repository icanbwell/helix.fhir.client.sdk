from typing import Protocol, Optional, Dict, Any, Tuple, List, Union, AsyncGenerator
from aiohttp import ClientSession, ClientResponse
from furl import furl

from helix_fhir_client_sdk.function_types import (
    RefreshTokenFunction,
    HandleStreamingChunkFunction,
    HandleStreamingResourcesFunction,
)
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


class FhirClientProtocol(Protocol):
    _id: Optional[Union[List[str], str]]
    _url: Optional[str]
    _resource: Optional[str]
    _obj_id: Optional[str]
    _retry_count: int
    _accept: str
    _content_type: str
    _accept_encoding: str
    _additional_request_headers: Dict[str, str]
    _action_payload: Optional[Dict[str, Any]]
    _log_level: Optional[str]
    _logger: Optional[Any]
    _internal_logger: Optional[Any]
    _use_data_streaming: bool
    _chunk_size: int
    _expand_fhir_bundle: bool
    _separate_bundle_resources: bool
    _extra_context_to_return: Optional[Dict[str, Any]]
    _access_token: Optional[str]
    _refresh_token_function: RefreshTokenFunction

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

    def _add_query_params(
        self,
        full_uri: furl,
        ids: Optional[List[str]],
        page_number: Optional[int],
        additional_parameters: Optional[List[str]],
        id_above: Optional[str],
    ) -> furl: ...

    async def _handle_rate_limiting(self, retry_after_text: str) -> None: ...

    async def _get_with_session_async(
        self,
        *,
        session: Optional[ClientSession],
        page_number: Optional[int] = None,
        ids: Optional[List[str]] = None,
        id_above: Optional[str] = None,
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction] = None,
        additional_parameters: Optional[List[str]] = None,
        fn_resource_chunk_handler: Optional[HandleStreamingResourcesFunction] = None,
    ) -> AsyncGenerator[FhirGetResponse, None]: ...

    def separate_bundle_resources(self, separate_bundle_resources: bool):  # type: ignore[no-untyped-def]
        ...

    def resource(self, resource: str):  # type: ignore[no-untyped-def]
        ...
