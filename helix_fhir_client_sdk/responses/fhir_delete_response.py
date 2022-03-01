from typing import Optional


class FhirDeleteResponse:
    def __init__(
        self,
        url: str,
        responses: str,
        error: Optional[str],
        access_token: Optional[str],
        status: int,
    ) -> None:
        """
        Class that encapsulates the response from FHIR server

        :param url: url that was being accessed
        :param responses: response text
        :param error: Any error returned by FHIR server
        :param access_token: access token that was used
        """
        self.url: str = url
        self.responses: str = responses
        self.error: Optional[str] = error
        self.access_token: Optional[str] = access_token
        self.status: int = status
