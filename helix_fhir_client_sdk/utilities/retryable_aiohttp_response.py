from typing import Dict

from aiohttp import StreamReader


class RetryableAioHttpResponse:
    def __init__(
        self,
        *,
        ok: bool,
        status: int,
        response_headers: Dict[str, str],
        response_text: str,
        content: StreamReader,
    ) -> None:
        self.ok: bool = ok
        self.status: int = status
        self.response_headers: Dict[str, str] = response_headers
        self.response_text: str = response_text
        self.content: StreamReader = content