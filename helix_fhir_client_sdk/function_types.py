import dataclasses
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

# This file contains contracts for callback functions


@runtime_checkable
class HandleBatchFunction(Protocol):
    async def __call__(self, resources_: list[dict[str, Any]], page_number: int | None) -> bool:
        """
        Handle a batch of data

        :param resources_: resources to handle
        :param page_number: page number
        :return: True if successful
        """
        ...


@runtime_checkable
class HandleStreamingChunkFunction(Protocol):
    async def __call__(
        self,
        line: bytes,
        chunk_number: int | None = None,
    ) -> bool:
        """
        Handle a streaming result

        :param line: line to handle
        :param chunk_number: chunk number
        :return: True if successful
        """
        ...


@runtime_checkable
class HandleErrorFunction(Protocol):
    async def __call__(self, *, error: str, response: str, page_number: int | None, url: str) -> bool:
        """
        Handle an error

        :param error: error message
        :param response: error details
        :param page_number: page number
        :return: True if successful
        """
        ...


@dataclasses.dataclass(slots=True)
class RefreshTokenResult:
    """
    Result of a token refresh
    """

    access_token: str | None
    """ New access token """

    expiry_date: datetime | None
    """ Expiry date of the new token """

    abort_request: bool | None
    """ If True, abort the request """


@runtime_checkable
class RefreshTokenFunction(Protocol):
    async def __call__(
        self,
        *,
        url: str | None,
        status_code: int | None,
        current_token: str | None,
        expiry_date: datetime | None,
        retry_count: int | None,
    ) -> RefreshTokenResult:
        """
        Refreshes a token and returns the new token. If the token cannot be refreshed, returns None.


        :param url: url we loaded
        :param status_code: status code of the response
        :param current_token: current token
        :param expiry_date: expiry date of the current token
        :param retry_count: retry count
        :return: result containing the new token and the new expiry date
        """
        ...


@runtime_checkable
class HandleStreamingResourcesFunction(Protocol):
    async def __call__(
        self,
        *,
        resources: list[dict[str, Any]] | None,
        chunk_number: int | None = None,
    ) -> bool:
        """
        Handle a streaming result

        :param resources: complete resources we've received so far
        :param chunk_number: chunk number
        :return: True if successful
        """
        ...


@dataclasses.dataclass(slots=True)
class TraceRequestResult:
    """
    Result of a request trace
    """

    abort_request: bool | None
    """ Whether to abort the request """


@runtime_checkable
class TraceRequestFunction(Protocol):
    async def __call__(
        self,
        *,
        ok: bool,
        url: str | None,
        status_code: int | None,
        access_token: str | None,
        expiry_date: datetime | None,
        retry_count: int | None,
        start_time: float | None,
        end_time: float | None,
        request_headers: dict[str, str] | None,
        response_headers: dict[str, str] | None,
    ) -> TraceRequestResult:
        """
        Called whenever we load a new url


        :param url: url we loaded
        :param status_code: status code of the response
        :param access_token: access token used in the request
        :param expiry_date: expiry date of the access token
        :param retry_count: retry count
        :param start_time: start time of the request (using time.time())
        :param end_time: end time of the request (using time.time())
        :return: new token or None
        """
        ...
