from typing import Optional


class FhirGetResponse:
    def __init__(
        self,
        request_id: Optional[str],
        url: str,
        responses: str,
        error: Optional[str],
        access_token: Optional[str],
        total_count: Optional[int],
        status: int,
        next_url: Optional[str] = None,
    ) -> None:
        """
        Class that encapsulates the response from FHIR server

        :param request_id: request id
        :param url: url that was being accessed
        :param responses: response text
        :param error: Any error returned by FHIR server
        :param access_token: access token that was used
        :param total_count: count of total records that match the provided query.
                            Only set if include_total_count was set to avoid expensive operation by server.
        """
        self.request_id: Optional[str] = request_id
        self.url: str = url
        self.responses: str = responses
        self.error: Optional[str] = error
        self.access_token: Optional[str] = access_token
        self.total_count: Optional[int] = total_count
        self.status: int = status
        self.next_url: Optional[str] = next_url
