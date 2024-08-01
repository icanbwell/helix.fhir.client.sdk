import asyncio
import json
from datetime import datetime
from typing import Optional, Dict, AsyncGenerator, List, cast, Any
from urllib import parse

from aiohttp import ClientResponse
from furl import furl

from helix_fhir_client_sdk.function_types import HandleStreamingChunkFunction
from helix_fhir_client_sdk.responses.fhir_client_protocol import FhirClientProtocol
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.utilities.ndjson_chunk_streaming_parser import (
    NdJsonChunkStreamingParser,
)


class FhirResponseMixin:
    def _build_full_url(
        self: FhirClientProtocol,
        ids: Optional[List[str]],
        page_number: Optional[int],
        additional_parameters: Optional[List[str]],
        id_above: Optional[str],
    ) -> str:
        full_uri = furl(self._url)
        full_uri /= self._resource
        if self._obj_id:
            full_uri /= parse.quote(str(self._obj_id), safe="")
        full_uri = self._add_query_params(
            full_uri, ids, page_number, additional_parameters, id_above
        )
        return cast(str, full_uri.url)

    # noinspection PyMethodMayBeStatic
    def _add_query_params(
        self,
        full_uri: furl,
        ids: Optional[List[str]],
        page_number: Optional[int],
        additional_parameters: Optional[List[str]],
        id_above: Optional[str],
    ) -> furl:
        # Add various query parameters to full_uri based on provided inputs
        return full_uri

    def _build_headers(self: FhirClientProtocol) -> Dict[str, str]:
        headers = {
            "Accept": self._accept,
            "Content-Type": self._content_type,
            "Accept-Encoding": self._accept_encoding,
        }
        headers.update(self._additional_request_headers)
        return headers

    async def _handle_successful_response(
        self: FhirClientProtocol,
        response: ClientResponse,
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction],
        full_url: str,
        access_token: Optional[str],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        nd_json_chunk_streaming_parser = NdJsonChunkStreamingParser()
        if self._use_data_streaming:
            chunk_number = 0
            chunk_bytes: bytes
            async for chunk_bytes in response.content.iter_chunked(self._chunk_size):
                chunk_number += 1
                if fn_handle_streaming_chunk:
                    await fn_handle_streaming_chunk(chunk_bytes, chunk_number)
                completed_resources = nd_json_chunk_streaming_parser.add_chunk(
                    chunk=chunk_bytes.decode("utf-8")
                )
                if completed_resources:
                    yield FhirGetResponse(
                        request_id=None,
                        url=full_url,
                        responses=json.dumps(completed_resources),
                        error=None,
                        access_token=access_token,
                        total_count=0,
                        status=response.status,
                        next_url=None,
                        extra_context_to_return=self._extra_context_to_return,
                        resource_type=self._resource,
                        id_=self._id,
                        response_headers=[],
                        chunk_number=chunk_number,
                    )
        else:
            resources_json: str = ""
            total_count: int = 0
            text = await response.text()
            if len(text) > 0:
                response_json: Dict[str, Any] = json.loads(text)
                if (
                    "resourceType" in response_json
                    and response_json["resourceType"] == "Bundle"
                ):
                    # get next url if present
                    if "link" in response_json:
                        links: List[Dict[str, Any]] = response_json.get("link", [])
                        next_links = [
                            link for link in links if link.get("relation") == "next"
                        ]
                        if len(next_links) > 0:
                            next_link: Dict[str, Any] = next_links[0]
                            next_url = next_link.get("url")

                # see if this is a Resource Bundle and un-bundle it
                if (
                    self._expand_fhir_bundle
                    and "resourceType" in response_json
                    and response_json["resourceType"] == "Bundle"
                ):
                    (
                        resources_json,
                        total_count,
                    ) = await self._expand_bundle_async(
                        resources_json,
                        response_json,
                        total_count,
                        access_token=access_token,
                        url=self._url or "",
                    )
                elif (
                    self._separate_bundle_resources
                    and "resourceType" in response_json
                    and response_json["resourceType"] != "Bundle"
                ):
                    # single resource was returned
                    resources_dict = {
                        f'{response_json["resourceType"].lower()}': [response_json],
                        "token": access_token,
                        "url": self._url,
                    }
                    if self._extra_context_to_return:
                        resources_dict.update(self._extra_context_to_return)

                    resources_json = json.dumps(resources_dict)
                else:
                    resources_json = text
            yield FhirGetResponse(
                request_id=None,
                url=full_url,
                responses=resources_json,
                error=None,
                access_token=self._access_token,
                total_count=total_count,
                status=response.status,
                next_url=None,
                extra_context_to_return=self._extra_context_to_return,
                resource_type=self._resource,
                id_=self._id,
                response_headers=[],
            )

    async def _handle_error_response(
        self: FhirClientProtocol,
        response: ClientResponse,
        full_url: str,
        retries_left: int,
        headers: Dict[str, str],
        access_token: Optional[str],
    ) -> FhirGetResponse:
        last_response_text = await self.get_safe_response_text_async(response)
        if response.status in (502, 504):
            if retries_left > 0:
                return FhirGetResponse(
                    request_id=None,
                    url=full_url,
                    responses="",
                    error="Retry",
                    access_token=access_token,
                    total_count=0,
                    status=response.status,
                    extra_context_to_return=self._extra_context_to_return,
                    resource_type=self._resource,
                    id_=self._id,
                    response_headers=[],
                )
        elif response.status == 429:
            retry_after_text = response.headers.getone("Retry-After")
            await self._handle_rate_limiting(retry_after_text)
            return FhirGetResponse(
                request_id=None,
                url=full_url,
                responses="",
                error="Retry",
                access_token=access_token,
                total_count=0,
                status=response.status,
                extra_context_to_return=self._extra_context_to_return,
                resource_type=self._resource,
                id_=self._id,
                response_headers=[],
            )
        return FhirGetResponse(
            request_id=None,
            url=full_url,
            responses=last_response_text,
            error="Error",
            access_token=access_token,
            total_count=0,
            status=response.status,
            extra_context_to_return=self._extra_context_to_return,
            resource_type=self._resource,
            id_=self._id,
            response_headers=[],
        )

    # noinspection PyMethodMayBeStatic
    async def _handle_rate_limiting(
        self: FhirClientProtocol, retry_after_text: str
    ) -> None:
        if retry_after_text.isnumeric():
            await asyncio.sleep(int(retry_after_text))
        else:
            wait_till = datetime.strptime(retry_after_text, "%a, %d %b %Y %H:%M:%S GMT")
            while datetime.utcnow() < wait_till:
                await asyncio.sleep(10)
