from typing import List, Dict, Any, Optional, Protocol


# This file contains contracts for callback functions
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


class HandleErrorFunction(Protocol):
    async def __call__(
        self, error: str, response: str, page_number: Optional[int]
    ) -> bool:
        """
        Handle an error

        :param error: error message
        :param response: error details
        :param page_number: page number
        :return: True if successful
        """
        ...


class RefreshTokenFunction(Protocol):
    async def __call__(
        self,
        auth_server_url: str,
        auth_scopes: Optional[List[str]],
        login_token: Optional[str],
    ) -> Optional[str]:
        """
        Refreshes a token and returns the new token. If the token cannot be refreshed, returns None.

        :param auth_server_url: url to auth server
        :param auth_scopes: scopes to refresh token for
        :param login_token: login token
        :return: new token or None
        """
        ...
