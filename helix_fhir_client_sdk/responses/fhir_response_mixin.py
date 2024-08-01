import asyncio
import json
from datetime import datetime
from typing import Optional, Dict, AsyncGenerator, List, Any
from urllib import parse

from aiohttp import ClientResponse
from furl import furl

from helix_fhir_client_sdk.function_types import HandleStreamingChunkFunction
from helix_fhir_client_sdk.responses.fhir_client_protocol import FhirClientProtocol
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.utilities.ndjson_chunk_streaming_parser import (
    NdJsonChunkStreamingParser,
)


class FhirResponseMixin(FhirClientProtocol):
    def _build_full_url(
        self,
        ids: Optional[List[str]],
        page_number: Optional[int],
        additional_parameters: Optional[List[str]],
        id_above: Optional[str],
    ) -> str:
        full_uri = furl(self._url)
        full_uri /= self._resource
        if self._obj_id:
            full_uri /= parse.quote(str(self._obj_id), safe="")
        full_url: str = self._add_query_params(
            full_uri, ids, page_number, additional_parameters, id_above
        )
        return full_url

    # noinspection PyMethodMayBeStatic
    def _add_query_params(
        self,
        full_uri: furl,
        ids: Optional[List[str]],
        page_number: Optional[int],
        additional_parameters: Optional[List[str]],
        id_above: Optional[str],
    ) -> str:
        if ids is not None and len(ids) > 0:
            if self._filter_by_resource:
                if self._filter_parameter:
                    # ?subject:Patient=27384972
                    full_uri.args[
                        f"{self._filter_parameter}:{self._filter_by_resource}"
                    ] = ",".join(sorted(ids))
                else:
                    # ?patient=27384972
                    full_uri.args[self._filter_by_resource.lower()] = ",".join(
                        sorted(ids)
                    )
            else:
                if len(ids) == 1 and not self._obj_id:
                    full_uri /= ids
                else:
                    full_uri.args["id"] = ",".join(sorted(ids))
            # add action to url
        if self._action:
            full_uri /= self._action
            # add a query for just desired properties
        if self._include_only_properties:
            full_uri.args["_elements"] = ",".join(self._include_only_properties)
        if self._page_size and (
            self._page_number is not None or page_number is not None
        ):
            # noinspection SpellCheckingInspection
            full_uri.args["_count"] = self._page_size
            # noinspection SpellCheckingInspection
            full_uri.args["_getpagesoffset"] = page_number or self._page_number

        if (
            not self._obj_id
            and (ids is None or self._filter_by_resource)
            and self._limit
            and self._limit >= 0
        ):
            full_uri.args["_count"] = self._limit

            # add any sort fields
        if self._sort_fields is not None:
            full_uri.args["_sort"] = ",".join([str(s) for s in self._sort_fields])

            # create full url by adding on any query parameters
        full_url: str = full_uri.url
        if additional_parameters:
            if len(full_uri.args) > 0:
                full_url += "&"
            else:
                full_url += "?"
            full_url += "&".join(additional_parameters)
        elif self._additional_parameters:
            if len(full_uri.args) > 0:
                full_url += "&"
            else:
                full_url += "?"
            full_url += "&".join(self._additional_parameters)

        if self._include_total:
            if len(full_uri.args) > 0:
                full_url += "&"
            else:
                full_url += "?"
            full_url += "_total=accurate"

        if self._filters and len(self._filters) > 0:
            if len(full_uri.args) > 0:
                full_url += "&"
            else:
                full_url += "?"
            full_url += "&".join(
                set([str(f) for f in self._filters])
            )  # remove any duplicates

        # have to be done here since this arg can be used twice
        if self._last_updated_before:
            if len(full_uri.args) > 0:
                full_url += "&"
            else:
                full_url += "?"
            full_url += f"_lastUpdated=lt{self._last_updated_before.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        if self._last_updated_after:
            if len(full_uri.args) > 0:
                full_url += "&"
            else:
                full_url += "?"
            full_url += f"_lastUpdated=ge{self._last_updated_after.strftime('%Y-%m-%dT%H:%M:%SZ')}"

        if id_above is not None:
            if len(full_uri.args) > 0:
                full_url += "&"
            else:
                full_url += "?"
            full_url += f"id:above={id_above}"
        return full_url

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": self._accept,
            "Content-Type": self._content_type,
            "Accept-Encoding": self._accept_encoding,
        }
        headers.update(self._additional_request_headers)
        return headers

    async def _handle_successful_response(
        self,
        response: ClientResponse,
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction],
        full_url: str,
        access_token: Optional[str],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        nd_json_chunk_streaming_parser = NdJsonChunkStreamingParser()
        if self._use_data_streaming:
            chunk_number = 0
            chunk_bytes: bytes
            try:
                async for chunk_bytes in response.content.iter_chunked(
                    self._chunk_size
                ):
                    chunk_number += 1
                    if fn_handle_streaming_chunk:
                        await fn_handle_streaming_chunk(chunk_bytes, chunk_number)
                    completed_resources = nd_json_chunk_streaming_parser.add_chunk(
                        chunk=chunk_bytes.decode("utf-8")
                    )
                    print(
                        f"Chunk {chunk_number}, Completed Resources: {completed_resources}, chunk: {chunk_bytes.decode('utf-8')}"
                    )
                    # Yield only if there are completed resources
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

            except Exception as e:
                print(f"Error processing chunk {chunk_number}: {e}")
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
        self,
        *,
        request_id: Optional[str],
        response: ClientResponse,
        full_url: str,
        retries_left: int,
        headers: Dict[str, str],
        response_headers: List[str],
        access_token: Optional[str],
    ) -> FhirGetResponse:
        last_response_text = await self.get_safe_response_text_async(response)
        if response.status == 404:  # not found
            last_response_text = await self.get_safe_response_text_async(
                response=response
            )
            if self._logger:
                self._logger.error(f"resource not found! {full_url}")
            return FhirGetResponse(
                request_id=request_id,
                url=full_url,
                responses=last_response_text,
                error="NotFound",
                access_token=self._access_token,
                total_count=0,
                status=response.status,
                extra_context_to_return=self._extra_context_to_return,
                resource_type=self._resource,
                id_=self._id,
                response_headers=response_headers,
            )
        elif response.status in (502, 504):
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
        elif response.status == 403:  # forbidden
            last_response_text = await self.get_safe_response_text_async(
                response=response
            )
            return FhirGetResponse(
                request_id=request_id,
                url=full_url,
                responses=await response.text(),
                error=None,
                access_token=self._access_token,
                total_count=0,
                status=response.status,
                extra_context_to_return=self._extra_context_to_return,
                resource_type=self._resource,
                id_=self._id,
                response_headers=response_headers,
            )
        elif response.status == 401:  # unauthorized
            last_response_text = await self.get_safe_response_text_async(
                response=response
            )
            if retries_left > 0 and (
                not self._exclude_status_codes_from_retry
                or response.status not in self._exclude_status_codes_from_retry
            ):
                current_access_token: Optional[str] = self._access_token
                try:
                    new_access_token = await self._refresh_token_function(
                        auth_server_url=self._auth_server_url,
                        auth_scopes=self._auth_scopes,
                        login_token=self._login_token,
                    )
                    if new_access_token:
                        self.set_access_token(new_access_token)
                    if not self._access_token:
                        # no ability to refresh auth token
                        return FhirGetResponse(
                            request_id=request_id,
                            url=full_url,
                            responses="",
                            error=last_response_text or "UnAuthorized",
                            access_token=current_access_token,
                            total_count=0,
                            status=response.status,
                            extra_context_to_return=self._extra_context_to_return,
                            resource_type=self._resource,
                            id_=self._id,
                            response_headers=response_headers,
                        )
                except Exception as ex:
                    # no ability to refresh auth token
                    return FhirGetResponse(
                        request_id=request_id,
                        url=full_url,
                        responses="",
                        error=str(ex),
                        access_token=current_access_token,
                        total_count=0,
                        status=response.status,
                        extra_context_to_return=self._extra_context_to_return,
                        resource_type=self._resource,
                        id_=self._id,
                        response_headers=response_headers,
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
    async def _handle_rate_limiting(self, retry_after_text: str) -> None:
        if retry_after_text.isnumeric():
            await asyncio.sleep(int(retry_after_text))
        else:
            wait_till = datetime.strptime(retry_after_text, "%a, %d %b %Y %H:%M:%S GMT")
            while datetime.utcnow() < wait_till:
                await asyncio.sleep(10)
