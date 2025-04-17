from collections import deque
from collections.abc import AsyncGenerator
from typing import Any, Optional

from helix_fhir_client_sdk.responses.merge.base_fhir_merge_resource_response_entry import (
    BaseFhirMergeResourceResponseEntry,
)


class FhirMergeResourceResponse:
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
        "successful",
        "response_text",
    ]

    def __init__(
        self,
        *,
        request_id: str | None,
        url: str,
        responses: deque[BaseFhirMergeResourceResponseEntry],
        error: str | None,
        access_token: str | None,
        status: int,
        response_text: str | None,
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
        self.responses: deque[BaseFhirMergeResourceResponseEntry] = responses
        self.error: str | None = error
        self.access_token: str | None = access_token
        self.status: int = status
        self.successful: bool = status == 200
        self.response_text: str | None = response_text

    def append(self, other: Optional["FhirMergeResourceResponse"]) -> None:
        """
        Appends another FhirMergeResponse to this one

        :param other: FhirMergeResponse to append
        """
        if other:
            self.responses = deque(list(self.responses) + list(other.responses))
            self.error = (self.error or "") + (other.error or "")
            self.successful = self.successful and other.successful

    @classmethod
    async def from_async_generator(
        cls, generator: AsyncGenerator["FhirMergeResourceResponse", None]
    ) -> Optional["FhirMergeResourceResponse"]:
        """
        Reads a generator of FhirGetResponse and returns a single FhirGetResponse by appending all the FhirGetResponse

        :param generator: generator of FhirGetResponse items
        :return: FhirGetResponse
        """
        result: FhirMergeResourceResponse | None = None
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
            "entries": [entry.to_dict() for entry in self.responses],
            "error": self.error,
            "access_token": self.access_token,
            "status": self.status,
            "response_text": self.response_text,
            "successful": self.successful,
        }
