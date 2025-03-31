from datetime import datetime
import json
from typing import Dict, Optional, List, cast, Any

from aiohttp import StreamReader

from helix_fhir_client_sdk.utilities.retryable_aiohttp_url_result import (
    RetryableAioHttpUrlResult,
)


class RetryableAioHttpResponse:
    """
    Response object for retryable aiohttp requests
    """

    __slots__ = [
        "ok",
        "status",
        "response_headers",
        "_response_text",
        "content",
        "use_data_streaming",
        "text_read",
        "results_by_url",
        "access_token",
        "access_token_expiry_date",
        "retry_count",
    ]

    def __init__(
        self,
        *,
        ok: bool,
        status: int,
        response_headers: Dict[str, str],
        response_text: str,
        content: StreamReader | None,
        use_data_streaming: Optional[bool],
        results_by_url: List[RetryableAioHttpUrlResult],
        access_token: Optional[str],
        access_token_expiry_date: Optional[datetime],
        retry_count: Optional[int]
    ) -> None:
        """
        Response object for retryable aiohttp requests


        """
        self.ok: bool = ok
        """ True if status is less than 400 """

        self.status: int = status
        """ Status code of the response """

        self.response_headers: Dict[str, str] = response_headers
        """ Headers of the response """

        self._response_text: str = response_text
        """ Text of the response """

        self.content: StreamReader | None = content
        """ Content of the response as a stream """

        self.use_data_streaming: Optional[bool] = use_data_streaming
        """ If the response should be read as a stream """

        self.text_read: Optional[str] = None
        """ Text of the response if the response is read as a stream """

        self.results_by_url: List[RetryableAioHttpUrlResult] = results_by_url
        """ Count of errors by status code """

        self.access_token: Optional[str] = access_token
        """ access token """

        self.access_token_expiry_date: Optional[datetime] = access_token_expiry_date
        """ access token expiry date"""

        self.retry_count: Optional[int] = retry_count
        """ retry count """

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

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the object to a dictionary

        :return: dictionary
        """
        return dict(
            ok=self.ok,
            status=self.status,
            response_headers=self.response_headers,
            response_text=self._response_text,
            content=self.content,
            use_data_streaming=self.use_data_streaming,
            text_read=self.text_read,
            results_by_url=[r.to_dict() for r in self.results_by_url],
            access_token=self.access_token,
            access_token_expiry_date=self.access_token_expiry_date,
            retry_count=self.retry_count,
        )
