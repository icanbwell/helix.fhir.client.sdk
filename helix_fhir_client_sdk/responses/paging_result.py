import dataclasses
from collections.abc import AsyncGenerator
from typing import Any, Optional

from helix_fhir_client_sdk.utilities.logging_decorators import log_execution_time


@dataclasses.dataclass(slots=True)
class PagingResult:
    """
    PagingResult class for encapsulating the response from FHIR server when paging resources
    """

    request_id: str | None
    resources: list[dict[str, Any]]
    page_number: int
    response_headers: list[str] | None

    @log_execution_time
    def append(self, other: Optional["PagingResult"]) -> None:
        """
        Appends another PagingResult to this one

        :param other: PagingResult to append
        """
        if other:
            self.resources.extend(other.resources)
            self.response_headers = (self.response_headers or []) + (other.response_headers or [])
            self.page_number = other.page_number
    
    @classmethod
    @log_execution_time
    async def from_async_generator(cls, generator: AsyncGenerator["PagingResult", None]) -> Optional["PagingResult"]:
        """
        Reads a generator of PagingResult and returns a single PagingResult by appending all the PagingResult

        :param generator: generator of PagingResult items
        :return: PagingResult
        """
        result: PagingResult | None = None
        async for value in generator:
            if not result:
                result = value
            else:
                result.append(value)
        return result
