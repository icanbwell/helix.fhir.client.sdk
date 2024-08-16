import json
from typing import Dict, Optional, List, cast

from aiohttp import StreamReader


class RetryableAioHttpResponse:
    def __init__(
        self,
        *,
        ok: bool,
        status: int,
        response_headers: Dict[str, str],
        response_text: str,
        content: StreamReader | None,
        use_data_streaming: Optional[bool],
    ) -> None:
        self.ok: bool = ok
        self.status: int = status
        self.response_headers: Dict[str, str] = response_headers
        self._response_text: str = response_text
        self.content: StreamReader | None = content
        self.use_data_streaming: Optional[bool] = use_data_streaming
        self.text_read: Optional[str] = None

    async def get_text_async(self) -> str:
        if self.content is None:
            return self._response_text
        if self.use_data_streaming:
            if self.text_read is None:
                # avoid reading the stream multiple times
                self.text_read = (await self.content.read()).decode("utf-8")
            return self.text_read
        else:
            return self._response_text

    async def json(self) -> Dict[str, str] | List[Dict[str, str]]:
        text = await self.get_text_async()
        return cast(Dict[str, str] | List[Dict[str, str]], json.loads(text))
