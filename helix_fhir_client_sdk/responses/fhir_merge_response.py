from typing import List, Optional, Dict, Any


class FhirMergeResponse:
    def __init__(
        self,
        url: str,
        responses: List[Dict[str, Any]],
        error: Optional[str],
        access_token: Optional[str],
    ) -> None:
        """
        Class that encapsulates a response to e $merge call to FHIR server

        :param url: url that was being accessed
        :param responses: list of responses
        :param error: Any error returned by FHIR server
        :param access_token: access token that was used
        """
        self.url: str = url
        self.responses: List[Dict[str, Any]] = responses
        self.error: Optional[str] = error
        self.access_token: Optional[str] = access_token
