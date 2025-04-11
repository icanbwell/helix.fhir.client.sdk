from typing import Optional, AsyncGenerator, Dict, Any


class FhirUpdateResponse:
    """
    FHIR Update Response class for encapsulating the response from FHIR server when updating resources
    """

    __slots__ = [
        "request_id",
        "url",
        "responses",
        "error",
        "access_token",
        "status",
        "resource_type",
    ]

    def __init__(
        self,
        *,
        request_id: Optional[str],
        url: str,
        responses: str,
        error: Optional[str],
        access_token: Optional[str],
        status: int,
        resource_type: Optional[str],
    ) -> None:
        """
        Class that encapsulates the response from FHIR server

        :param request_id: request id
        :param url: url that was being accessed
        :param responses: response text
        :param error: Any error returned by FHIR server
        :param access_token: access token that was used
        """
        self.request_id: Optional[str] = request_id
        self.url: str = url
        self.responses: str = responses
        self.error: Optional[str] = error
        self.access_token: Optional[str] = access_token
        self.status: int = status
        self.resource_type: Optional[str] = resource_type

    def append(self, other: Optional["FhirUpdateResponse"]) -> None:
        """
        Appends another FhirUpdateResponse to this one

        :param other: FhirUpdateResponse to append
        """
        if other:
            self.responses += other.responses
            self.error = (self.error or "") + (other.error or "")

    @classmethod
    async def from_async_generator(
        cls, generator: AsyncGenerator["FhirUpdateResponse", None]
    ) -> Optional["FhirUpdateResponse"]:
        """
        Reads a generator of FhirUpdateResponse and returns a single FhirUpdateResponse by appending all the FhirUpdateResponse

        :param generator: generator of FhirUpdateResponse items
        :return: FhirUpdateResponse
        """
        result: FhirUpdateResponse | None = None
        async for value in generator:
            if not result:
                result = value
            else:
                result.append(value)
        return result

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the FhirUpdateResponse to a dictionary

        :return: dictionary representation of the FhirUpdateResponse
        """
        return {
            "request_id": self.request_id,
            "url": self.url,
            "responses": self.responses,
            "error": self.error,
            "access_token": self.access_token,
            "status": self.status,
            "resource_type": self.resource_type,
        }
