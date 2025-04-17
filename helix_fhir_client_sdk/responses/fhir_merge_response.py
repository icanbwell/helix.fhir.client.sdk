from collections.abc import AsyncGenerator
from typing import Any, Optional


class FhirMergeResponse:
    """
    FHIR Merge Response class for encapsulating the response from FHIR server when merging resources
    """

    __slots__ = [
        "request_id",
        "url",
        "responses",
        "error",
        "access_token",
        "status",
        "data",
        "successful",
    ]

    def __init__(
        self,
        *,
        request_id: str | None,
        url: str,
        responses: list[dict[str, Any]],
        error: str | None,
        access_token: str | None,
        status: int,
        json_data: str,
    ) -> None:
        """
        Class that encapsulates a response to e $merge call to FHIR server

        :param url: url that was being accessed
        :param responses: list of responses
        :param error: Any error returned by FHIR server
        :param access_token: access token that was used
        """
        self.request_id: str | None = request_id
        self.url: str = url
        self.responses: list[dict[str, Any]] = responses
        self.error: str | None = error
        self.access_token: str | None = access_token
        self.status: int = status
        self.data: str = json_data
        self.successful: bool = status != 200

    def append(self, other: Optional["FhirMergeResponse"]) -> None:
        """
        Appends another FhirMergeResponse to this one

        :param other: FhirMergeResponse to append
        """
        if other:
            self.responses.extend(other.responses)
            self.error = (self.error or "") + (other.error or "")
            self.successful = self.successful and other.successful

    @classmethod
    async def from_async_generator(
        cls, generator: AsyncGenerator["FhirMergeResponse", None]
    ) -> Optional["FhirMergeResponse"]:
        """
        Reads a generator of FhirGetResponse and returns a single FhirGetResponse by appending all the FhirGetResponse

        :param generator: generator of FhirGetResponse items
        :return: FhirGetResponse
        """
        result: FhirMergeResponse | None = None
        async for value in generator:
            if not result:
                result = value
            else:
                result.append(value)

        assert result
        return result

    def to_dict(self) -> dict[str, Any]:
        """
        Converts the FhirMergeResponse to a dictionary

        :return: dictionary representation of the FhirMergeResponse
        """
        return {
            "request_id": self.request_id,
            "url": self.url,
            "responses": self.responses,
            "error": self.error,
            "access_token": self.access_token,
            "status": self.status,
            "data": self.data,
            "successful": self.successful,
        }
