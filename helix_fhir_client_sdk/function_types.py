from typing import Callable, List, Dict, Any, Optional, Awaitable

HandleBatchFunction = Callable[[List[Dict[str, Any]], Optional[int]], Awaitable[bool]]
HandleStreamingChunkFunction = Callable[[bytes, Optional[int]], Awaitable[bool]]
HandleErrorFunction = Callable[[str, str, Optional[int]], Awaitable[bool]]

RefreshTokenFunction = Callable[
    [str, Optional[List[str]], Optional[str]], Awaitable[Optional[str]]
]
"""
Refreshes a token and returns the new token. If the token cannot be refreshed, returns None.

:param auth_server_url: url to auth server
:param scopes: scopes to refresh token for
:param login_token: login token
:return: new token or None
"""
