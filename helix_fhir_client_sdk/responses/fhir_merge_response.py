from typing import List, Optional, Dict, Any, AsyncGenerator


class FhirMergeResponse:
    def __init__(
        self,
        *,
        request_id: Optional[str],
        url: str,
        responses: List[Dict[str, Any]],
        error: Optional[str],
        access_token: Optional[str],
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
        self.request_id: Optional[str] = request_id
        self.url: str = url
        self.responses: List[Dict[str, Any]] = responses
        self.error: Optional[str] = error
        self.access_token: Optional[str] = access_token
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
