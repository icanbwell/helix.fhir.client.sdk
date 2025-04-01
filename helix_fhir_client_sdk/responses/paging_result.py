import dataclasses
from typing import List, Dict, Any, Optional, AsyncGenerator


@dataclasses.dataclass(slots=True)
class PagingResult:
    """
    PagingResult class for encapsulating the response from FHIR server when paging resources
    """

    request_id: Optional[str]
    resources: List[Dict[str, Any]]
    page_number: int
    response_headers: Optional[List[str]]

    def append(self, other: Optional["PagingResult"]) -> None:
        """
        Appends another PagingResult to this one

        :param other: PagingResult to append
        """
        if other:
            self.resources.extend(other.resources)
            self.response_headers = (self.response_headers or []) + (
                other.response_headers or []
            )
            self.page_number = other.page_number

    @classmethod
    async def from_async_generator(
        cls, generator: AsyncGenerator["PagingResult", None]
    ) -> Optional["PagingResult"]:
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
