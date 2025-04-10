import dataclasses
from datetime import datetime
from typing import List, Dict, Any, Optional, Protocol, runtime_checkable


# This file contains contracts for callback functions


@runtime_checkable
class HandleBatchFunction(Protocol):
    async def __call__(
        self, resources_: List[Dict[str, Any]], page_number: Optional[int]
    ) -> bool:
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
        chunk_number: Optional[int] = None,
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
    async def __call__(
        self, *, error: str, response: str, page_number: Optional[int], url: str
    ) -> bool:
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

    access_token: Optional[str]
    """ New access token """

    expiry_date: Optional[datetime]
    """ Expiry date of the new token """

    abort_request: Optional[bool]
    """ If True, abort the request """


@runtime_checkable
class RefreshTokenFunction(Protocol):
    async def __call__(
        self,
        *,
        url: Optional[str],
        status_code: Optional[int],
        current_token: Optional[str],
        expiry_date: Optional[datetime],
        retry_count: Optional[int],
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
        resources: Optional[List[Dict[str, Any]]],
        chunk_number: Optional[int] = None,
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

    abort_request: Optional[bool]
    """ Whether to abort the request """


@runtime_checkable
class TraceRequestFunction(Protocol):
    async def __call__(
        self,
        *,
        ok: bool,
        url: Optional[str],
        status_code: Optional[int],
        access_token: Optional[str],
        expiry_date: Optional[datetime],
        retry_count: Optional[int],
        start_time: Optional[float],
        end_time: Optional[float],
        request_headers: Optional[Dict[str, str]],
        response_headers: Optional[Dict[str, str]],
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
