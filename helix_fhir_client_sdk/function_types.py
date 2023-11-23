from typing import Callable, List, Dict, Any, Optional, Awaitable, Protocol

HandleBatchFunction = Callable[[List[Dict[str, Any]], Optional[int]], Awaitable[bool]]
HandleStreamingChunkFunction = Callable[[bytes, Optional[int]], Awaitable[bool]]
HandleErrorFunction = Callable[[str, str, Optional[int]], Awaitable[bool]]


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
