import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable, Type, Union

import async_timeout
from aiohttp import ClientResponse, ClientError, ClientResponseError, ClientSession

from helix_fhir_client_sdk.function_types import SimpleRefreshTokenFunction
from helix_fhir_client_sdk.utilities.retryable_aiohttp_response import (
    RetryableAioHttpResponse,
)


class RetryableAioHttpClient:
    def __init__(
        self,
        *,
        retries: int = 3,
        timeout_in_seconds: Optional[float] = None,
        backoff_factor: float = 0.5,
        retry_status_codes: Optional[List[int]] = None,
        simple_refresh_token_func: Optional[SimpleRefreshTokenFunction] = None,
        fn_get_session: Optional[Callable[[], ClientSession]] = None,
        exclude_status_codes_from_retry: List[int] | None = None,
        use_data_streaming: Optional[bool],
        compress: Optional[bool] = False,
        send_data_as_chunked: Optional[bool] = None,
        throw_exception_on_error: bool = True,
    ) -> None:
        self.retries: int = retries
        self.timeout_in_seconds: Optional[float] = timeout_in_seconds
        self.backoff_factor: float = backoff_factor
        self.retry_status_codes: Optional[List[int]] = (
            retry_status_codes
            if retry_status_codes is not None
            else [500, 502, 503, 504]
        )
        self.simple_refresh_token_func: Optional[SimpleRefreshTokenFunction] = (
            simple_refresh_token_func
        )
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
        retry_attempts = -1
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
                    response: ClientResponse = await self.session.request(
                        method,
                        url,
                        **kwargs,
                    )
                    if response.ok:
                        return RetryableAioHttpResponse(
                            ok=response.ok,
                            status=response.status,
                            response_headers={
                                k: v for k, v in response.headers.items()
                            },
                            response_text=(
                                await self.get_safe_response_text_async(
                                    response=response
                                )
                                if not self.use_data_streaming
                                else ""
                            ),
                            content=response.content,
                            use_data_streaming=self.use_data_streaming,
                        )
                    elif (
                        self.exclude_status_codes_from_retry
                        and response.status in self.exclude_status_codes_from_retry
                    ):
                        return RetryableAioHttpResponse(
                            ok=response.ok,
                            status=response.status,
                            response_headers={
                                k: v for k, v in response.headers.items()
                            },
                            response_text=await self.get_safe_response_text_async(
                                response=response
                            ),
                            content=response.content,
                            use_data_streaming=self.use_data_streaming,
                        )
                    elif response.status == 400:
                        return RetryableAioHttpResponse(
                            ok=response.ok,
                            status=response.status,
                            response_headers={
                                k: v for k, v in response.headers.items()
                            },
                            response_text=await self.get_safe_response_text_async(
                                response=response
                            ),
                            content=response.content,
                            use_data_streaming=self.use_data_streaming,
                        )
                    elif response.status in [403, 404]:
                        return RetryableAioHttpResponse(
                            ok=response.ok,
                            status=response.status,
                            response_headers={
                                k: v for k, v in response.headers.items()
                            },
                            response_text=await self.get_safe_response_text_async(
                                response=response
                            ),
                            content=response.content,
                            use_data_streaming=self.use_data_streaming,
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
                            headers=response.headers,
                            history=response.history,
                            request_info=response.request_info,
                        )
                    elif response.status == 401 and self.simple_refresh_token_func:
                        # Call the token refresh function if status code is 401
                        access_token = await self.simple_refresh_token_func()
                        if not headers:
                            headers = {}
                        headers["Authorization"] = f"Bearer {access_token}"
                        if retry_attempts >= self.retries:
                            raise ClientResponseError(
                                status=response.status,
                                message="Unauthorized",
                                headers=response.headers,
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
                                headers=response.headers,
                                history=response.history,
                                request_info=response.request_info,
                            )
                        else:
                            return RetryableAioHttpResponse(
                                ok=response.ok,
                                status=response.status,
                                response_headers={
                                    k: v for k, v in response.headers.items()
                                },
                                response_text=await self.get_safe_response_text_async(
                                    response=response
                                ),
                                content=response.content,
                                use_data_streaming=self.use_data_streaming,
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

    async def delete(self, *, url: str, **kwargs: Any) -> RetryableAioHttpResponse:
        return await self.fetch(url=url, method="DELETE", **kwargs)

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
