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


@dataclasses.dataclass
class RefreshTokenResult:
    access_token: Optional[str]
    expiry_date: Optional[datetime]


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

        :return: new token or None
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


@runtime_checkable
class TraceFunction(Protocol):
    async def __call__(
        self,
        *,
        url: Optional[str],
        status_code: Optional[int],
        access_token: Optional[str],
        expiry_date: Optional[datetime],
        retry_count: Optional[int],
    ) -> None:
        """
        Called whenever we load a new url

        :return: new token or None
        """
        ...
