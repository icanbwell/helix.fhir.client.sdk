import asyncio
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable, Type, Union, cast

import async_timeout
from aiohttp import ClientResponse, ClientError, ClientResponseError, ClientSession
from multidict import MultiMapping

from helix_fhir_client_sdk.function_types import (
    RefreshTokenFunction,
    RefreshTokenResult,
    TraceRequestFunction,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_response import (
    RetryableAioHttpResponse,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_url_result import (
    RetryableAioHttpUrlResult,
)


class RetryableAioHttpClient:
    def __init__(
        self,
        *,
        retries: int = 3,
        timeout_in_seconds: Optional[float] = None,
        backoff_factor: float = 0.5,
        retry_status_codes: Optional[List[int]] = None,
        refresh_token_func: Optional[RefreshTokenFunction],
        tracer_request_func: Optional[TraceRequestFunction],
        fn_get_session: Optional[Callable[[], ClientSession]] = None,
        exclude_status_codes_from_retry: List[int] | None = None,
        use_data_streaming: Optional[bool],
        compress: Optional[bool] = False,
        send_data_as_chunked: Optional[bool] = None,
        throw_exception_on_error: bool = True,
        log_all_url_results: bool = False,
        access_token: Optional[str],
        access_token_expiry_date: Optional[datetime],
    ) -> None:
        """
        RetryableClient provides a way to make HTTP calls with automatic retry and automatic refreshing of access tokens

        """
        self.retries: int = retries
        self.timeout_in_seconds: Optional[float] = timeout_in_seconds
        self.backoff_factor: float = backoff_factor
        self.retry_status_codes: Optional[List[int]] = (
            retry_status_codes
            if retry_status_codes is not None
            else [500, 502, 503, 504]
        )
        self.refresh_token_func_async: Optional[RefreshTokenFunction] = (
            refresh_token_func
        )
        self.trace_function_async: Optional[TraceRequestFunction] = tracer_request_func
        self.fn_get_session: Callable[[], ClientSession] = (
            fn_get_session if fn_get_session is not None else lambda: ClientSession()
        )
        self.exclude_status_codes_from_retry: List[int] | None = (
            exclude_status_codes_from_retry
        )
        self.use_data_streaming: Optional[bool] = use_data_streaming
        self.send_data_as_chunked: Optional[bool] = send_data_as_chunked
        self.compress: Optional[bool] = compress
        self.session: Optional[ClientSession] = None
        self._throw_exception_on_error: bool = throw_exception_on_error
        self.log_all_url_results: bool = log_all_url_results
        self.access_token: Optional[str] = access_token
        self.access_token_expiry_date: Optional[datetime] = access_token_expiry_date

    async def __aenter__(self) -> "RetryableAioHttpClient":
        self.session = self.fn_get_session()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Union[Type[BaseException], None]],
    ) -> None:
        if self.session is not None:
            await self.session.close()

    @staticmethod
    async def get_safe_response_text_async(
        *, response: Optional[ClientResponse]
    ) -> str:
        """
        This method is responsible for getting the response text from the response object.

        :param response: The response object from the FHIR server.
        """
        try:
            return (
                await response.text() if (response and response.status != 504) else ""
            )
        except Exception as e:
            return str(e)

    async def fetch(
        self,
        *,
        url: str,
        method: str = "GET",
        headers: Dict[str, str] | None,
        **kwargs: Any,
    ) -> RetryableAioHttpResponse:
        retry_attempts: int = -1
        results_by_url: List[RetryableAioHttpUrlResult] = []
        access_token: Optional[str] = self.access_token
        expiry_date: Optional[datetime] = self.access_token_expiry_date

        # run with retry
        while retry_attempts < self.retries:
            retry_attempts += 1
            try:
                if headers:
                    kwargs["headers"] = headers
                # if there is no data then remove from kwargs so as not to confuse aiohttp
                if "data" in kwargs and kwargs["data"] is None:
                    del kwargs["data"]
                # compression and chunked can only be enabled if there is content sent
                if "data" in kwargs and kwargs["data"] is not None:
                    if self.send_data_as_chunked:
                        kwargs["chunked"] = self.send_data_as_chunked
                    if self.compress:
                        kwargs["compress"] = self.compress
                assert self.session is not None
                async with async_timeout.timeout(self.timeout_in_seconds):
                    start_time: float = time.time()
                    response: ClientResponse = await self.session.request(
                        method,
                        url,
                        **kwargs,
                    )
                    # Append the result to the list of results
                    if self.log_all_url_results:
                        results_by_url.append(
                            RetryableAioHttpUrlResult(
                                ok=response.ok,
                                url=url,
                                status_code=response.status,
                                retry_count=retry_attempts,
                                start_time=start_time,
                                end_time=time.time(),
                            )
                        )
                    response_headers: Dict[str, str] = {
                        k: ",".join(response.headers.getall(k))
                        for k in response.headers.keys()
                    }
                    response_headers_multi_mapping: MultiMapping[str] = cast(
                        MultiMapping[str], response.headers
                    )

                    if self.trace_function_async:
                        request_headers: Dict[str, str] = {
                            k: ",".join(response.request_info.headers.getall(k))
                            for k in response.request_info.headers.keys()
                        }
                        await self.trace_function_async(
                            ok=response.ok,
                            url=url,
                            status_code=response.status,
                            access_token=access_token,
                            expiry_date=expiry_date,
                            retry_count=retry_attempts,
                            start_time=start_time,
                            end_time=time.time(),
                            request_headers=request_headers,
                            response_headers=response_headers,
                        )

                    if response.ok:
                        # If the response is successful, return the response
                        return RetryableAioHttpResponse(
                            ok=response.ok,
                            status=response.status,
                            response_headers=response_headers,
                            response_text=(
                                await self.get_safe_response_text_async(
                                    response=response
                                )
                                if not self.use_data_streaming
                                else ""
                            ),
                            content=response.content,
                            use_data_streaming=self.use_data_streaming,
                            results_by_url=results_by_url,
                            access_token=access_token,
                            access_token_expiry_date=expiry_date,
                            retry_count=retry_attempts,
                        )
                    elif (
                        self.exclude_status_codes_from_retry
                        and response.status in self.exclude_status_codes_from_retry
                    ):
                        return RetryableAioHttpResponse(
                            ok=response.ok,
                            status=response.status,
                            response_headers=response_headers,
                            response_text=await self.get_safe_response_text_async(
                                response=response
                            ),
                            content=response.content,
                            use_data_streaming=self.use_data_streaming,
                            results_by_url=results_by_url,
                            access_token=access_token,
                            access_token_expiry_date=expiry_date,
                            retry_count=retry_attempts,
                        )
                    elif response.status == 400:
                        return RetryableAioHttpResponse(
                            ok=response.ok,
                            status=response.status,
                            response_headers=response_headers,
                            response_text=await self.get_safe_response_text_async(
                                response=response
                            ),
                            content=response.content,
                            use_data_streaming=self.use_data_streaming,
                            results_by_url=results_by_url,
                            access_token=access_token,
                            access_token_expiry_date=expiry_date,
                            retry_count=retry_attempts,
                        )
                    elif response.status in [403, 404]:
                        return RetryableAioHttpResponse(
                            ok=response.ok,
                            status=response.status,
                            response_headers=response_headers,
                            response_text=await self.get_safe_response_text_async(
                                response=response
                            ),
                            content=response.content,
                            use_data_streaming=self.use_data_streaming,
                            results_by_url=results_by_url,
                            access_token=access_token,
                            access_token_expiry_date=expiry_date,
                            retry_count=retry_attempts,
                        )
                    elif response.status == 429:
                        await self._handle_429(response=response, full_url=url)
                    elif (
                        self.retry_status_codes
                        and response.status in self.retry_status_codes
                    ):
                        raise ClientResponseError(
                            status=response.status,
                            message="Retryable status code received",
                            headers=response_headers_multi_mapping,
                            history=response.history,
                            request_info=response.request_info,
                        )
                    elif response.status == 401 and self.refresh_token_func_async:
                        # Call the token refresh function if status code is 401
                        refresh_token_result: RefreshTokenResult = (
                            await self.refresh_token_func_async(
                                current_token=access_token,
                                expiry_date=expiry_date,
                                url=url,
                                status_code=response.status,
                                retry_count=retry_attempts,
                            )
                        )
                        if (
                            refresh_token_result.abort_request
                            or refresh_token_result.access_token is None
                        ):
                            return RetryableAioHttpResponse(
                                ok=False,
                                status=401,
                                response_headers={},
                                response_text="Unauthorized",
                                content=None,
                                use_data_streaming=self.use_data_streaming,
                                results_by_url=results_by_url,
                                access_token=access_token,
                                access_token_expiry_date=expiry_date,
                                retry_count=retry_attempts,
                            )
                        else:  # we got a valid token
                            access_token = refresh_token_result.access_token
                            expiry_date = refresh_token_result.expiry_date
                            if not headers:
                                headers = {}
                            headers["Authorization"] = f"Bearer {access_token}"
                            if retry_attempts >= self.retries:
                                raise ClientResponseError(
                                    status=response.status,
                                    message="Unauthorized",
                                    headers=response_headers_multi_mapping,
                                    history=response.history,
                                    request_info=response.request_info,
                                )
                            await asyncio.sleep(
                                self.backoff_factor * (2 ** (retry_attempts - 1))
                            )
                    else:
                        if self._throw_exception_on_error:
                            raise ClientResponseError(
                                status=response.status,
                                message="Non-retryable status code received",
                                headers=response_headers_multi_mapping,
                                history=response.history,
                                request_info=response.request_info,
                            )
                        else:
                            return RetryableAioHttpResponse(
                                ok=response.ok,
                                status=response.status,
                                response_headers=response_headers,
                                response_text=await self.get_safe_response_text_async(
                                    response=response
                                ),
                                content=response.content,
                                use_data_streaming=self.use_data_streaming,
                                results_by_url=results_by_url,
                                access_token=access_token,
                                access_token_expiry_date=expiry_date,
                                retry_count=retry_attempts,
                            )
            except (ClientError, asyncio.TimeoutError) as e:
                if retry_attempts >= self.retries:
                    if self._throw_exception_on_error:
                        raise
                    else:
                        return RetryableAioHttpResponse(
                            ok=False,
                            status=500,
                            response_headers={},
                            response_text=str(e),
                            content=None,
                            use_data_streaming=self.use_data_streaming,
                            results_by_url=results_by_url,
                            access_token=access_token,
                            access_token_expiry_date=expiry_date,
                            retry_count=retry_attempts,
                        )
                await asyncio.sleep(self.backoff_factor * (2 ** (retry_attempts - 1)))
            except Exception as e:
                if self._throw_exception_on_error:
                    raise
                else:
                    return RetryableAioHttpResponse(
                        ok=False,
                        status=500,
                        response_headers={},
                        response_text=str(e),
                        content=None,
                        use_data_streaming=self.use_data_streaming,
                        results_by_url=results_by_url,
                        access_token=access_token,
                        access_token_expiry_date=expiry_date,
                        retry_count=retry_attempts,
                    )

        # Raise an exception if all retries fail
        raise Exception("All retries failed")

    async def get(
        self, *, url: str, headers: Optional[Dict[str, str]] = None, **kwargs: Any
    ) -> RetryableAioHttpResponse:
        return await self.fetch(url=url, method="GET", headers=headers, **kwargs)

    async def post(
        self,
        *,
        url: str,
        headers: Optional[Dict[str, str]],
        data: Optional[str] = None,
        json: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> RetryableAioHttpResponse:
        if data is not None:
            kwargs["data"] = data
        elif json is not None:
            kwargs["json"] = json
        return await self.fetch(url=url, method="POST", headers=headers, **kwargs)

    async def patch(
        self,
        *,
        url: str,
        headers: Optional[Dict[str, str]],
        data: Optional[str] = None,
        json: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> RetryableAioHttpResponse:
        if data is not None:
            kwargs["data"] = data
        elif json is not None:
            kwargs["json"] = json
        return await self.fetch(url=url, method="PATCH", headers=headers, **kwargs)

    async def put(
        self,
        *,
        url: str,
        headers: Optional[Dict[str, str]],
        data: Optional[str] = None,
        json: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> RetryableAioHttpResponse:
        if data is not None:
            kwargs["data"] = data
        elif json is not None:
            kwargs["json"] = json
        return await self.fetch(url=url, method="PUT", headers=headers, **kwargs)

    async def delete(
        self, *, headers: Optional[Dict[str, str]], url: str, **kwargs: Any
    ) -> RetryableAioHttpResponse:
        return await self.fetch(url=url, headers=headers, method="DELETE", **kwargs)

    @staticmethod
    async def _handle_429(*, response: ClientResponse, full_url: str) -> None:
        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/429
        # read the Retry-After header
        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Retry-After
        retry_after_text: str = str(response.headers.get("Retry-After", ""))
        if retry_after_text:
            # noinspection PyBroadException
            try:
                if retry_after_text.isnumeric():  # it is number of seconds
                    await asyncio.sleep(int(retry_after_text))
                else:
                    wait_till: datetime = datetime.strptime(
                        retry_after_text, "%a, %d %b %Y %H:%M:%S GMT"
                    )
                    # Ensure the parsed time is in UTC
                    wait_till = wait_till.replace(tzinfo=timezone.utc)

                    # Calculate the time difference
                    time_diff = (wait_till - datetime.now(timezone.utc)).total_seconds()

                    # If the time difference is positive, sleep for that amount of time
                    if time_diff > 0:
                        await asyncio.sleep(time_diff)
            except Exception:
                # if there was some exception parsing the Retry-After header, sleep for 60 seconds
                await asyncio.sleep(60)
        else:
            await asyncio.sleep(60)
