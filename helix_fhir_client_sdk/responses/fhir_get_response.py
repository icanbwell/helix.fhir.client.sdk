from typing import List, Optional


class FhirGetResponse:
    def __init__(self, url: str, responses: List[str], error: Optional[str]) -> None:
        self.url: str = url
        self.responses: List[str] = responses
        self.error: Optional[str] = error
