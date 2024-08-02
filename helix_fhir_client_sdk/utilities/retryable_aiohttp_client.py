import asyncio
from typing import Optional, Dict, Any, List

import aiohttp
import async_timeout
from aiohttp import ClientSession, ClientResponse

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
        session: Optional[aiohttp.ClientSession] = None,
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
        self.session: Optional[ClientSession] = session

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
        retry_attempts = 0
        while retry_attempts < self.retries:
            try:
                if self.session is None:
                    self.session = aiohttp.ClientSession()
                async with async_timeout.timeout(self.timeout_in_seconds):
                    response = await self.session.request(
                        method, url, headers=headers, **kwargs
                    )
                    if response.ok:
                        return RetryableAioHttpResponse(
                            status=response.status,
                            response_headers={
                                k: v for k, v in response.headers.items()
                            },
                            response_text=await self.get_safe_response_text_async(
                                response=response
                            ),
                            content=response.content,
                        )
                    elif response.status == 404:
                        return RetryableAioHttpResponse(
                            status=response.status,
                            response_headers={
                                k: v for k, v in response.headers.items()
                            },
                            response_text=await self.get_safe_response_text_async(
                                response=response
                            ),
                            content=response.content,
                        )
                    elif (
                        self.retry_status_codes
                        and response.status in self.retry_status_codes
                    ):
                        raise aiohttp.ClientResponseError(
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
                            raise aiohttp.ClientResponseError(
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
                        response.raise_for_status()
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                retry_attempts += 1
                if retry_attempts == self.retries:
                    raise e
                await asyncio.sleep(self.backoff_factor * (2 ** (retry_attempts - 1)))

        # Raise an exception if all retries fail
        raise Exception("All retries failed")

    async def get(
        self, *, url: str, headers: Optional[Dict[str, str]], **kwargs: Any
    ) -> RetryableAioHttpResponse:
        return await self.fetch(url=url, method="GET", headers=headers, **kwargs)

    async def post(
        self,
        *,
        url: str,
        headers: Optional[Dict[str, str]],
        data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> RetryableAioHttpResponse:
        if data is not None:
            kwargs["json"] = data
        return await self.fetch(url=url, method="POST", headers=headers, **kwargs)

    async def delete(self, *, url: str, **kwargs: Any) -> RetryableAioHttpResponse:
        return await self.fetch(url=url, method="DELETE", **kwargs)
