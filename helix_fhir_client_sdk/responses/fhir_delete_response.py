from typing import Optional


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
