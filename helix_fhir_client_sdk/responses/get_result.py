import dataclasses
from collections.abc import AsyncGenerator
from typing import Any, Optional


@dataclasses.dataclass(slots=True)
class GetResult:
    """
    GetResult class for encapsulating the response from FHIR server when getting resources
    """

    request_id: str | None
    resources: list[dict[str, Any]]
    response_headers: list[str] | None

    def append(self, other: Optional["GetResult"]) -> None:
        """
        Appends another GetResult to this one

        :param other: GetResult to append
        """
        if other:
            self.resources.extend(other.resources)
            self.response_headers = (self.response_headers or []) + (other.response_headers or [])

    @classmethod
    async def from_async_generator(cls, generator: AsyncGenerator["GetResult", None]) -> Optional["GetResult"]:
        """
        Reads a generator of GetResult and returns a single GetResult by appending all the GetResult

        :param generator: generator of GetResult items
        :return: GetResult
        """
        result: GetResult | None = None
        async for value in generator:
            if not result:
                result = value
            else:
                result.append(value)
        return result
