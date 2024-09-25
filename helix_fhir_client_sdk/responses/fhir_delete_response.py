from typing import Optional, AsyncGenerator


class FhirDeleteResponse:
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
        count: Optional[int] = None,
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
        """ Response text """
        self.responses: str = responses
        self.error: Optional[str] = error
        self.access_token: Optional[str] = access_token
        self.status: int = status
        """ Number of resources deleted """
        self.count: Optional[int] = count
        self.resource_type: Optional[str] = resource_type

    def append(self, other: Optional["FhirDeleteResponse"]) -> None:
        """
        Appends another FhirDeleteResponse to this one

        :param other: FhirDeleteResponse to append
        """
        if other:
            self.responses += other.responses
            self.error = (self.error or "") + (other.error or "")
            self.count = (self.count or 0) + (other.count or 0)

    @classmethod
    async def from_async_generator(
        cls, generator: AsyncGenerator["FhirDeleteResponse", None]
    ) -> Optional["FhirDeleteResponse"]:
        """
        Reads a generator of FhirDeleteResponse and returns a single FhirDeleteResponse by appending all the FhirDeleteResponse

        :param generator: generator of FhirDeleteResponse items
        :return: FhirDeleteResponse
        """
        result: FhirDeleteResponse | None = None
        async for value in generator:
            if not result:
                result = value
            else:
                result.append(value)
        return result
