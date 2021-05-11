from typing import Optional


class FhirGetResponse:
    def __init__(
        self,
        url: str,
        responses: str,
        error: Optional[str],
        access_token: Optional[str],
    ) -> None:
        self.url: str = url
        self.responses: str = responses
        self.error: Optional[str] = error
        self.access_token: Optional[str] = access_token
