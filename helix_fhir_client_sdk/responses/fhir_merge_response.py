from typing import List, Optional, Dict, Any


class FhirMergeResponse:
    def __init__(
        self, url: str, responses: List[Dict[str, Any]], error: Optional[str]
    ) -> None:
        self.url: str = url
        self.responses: List[Dict[str, Any]] = responses
        self.error: Optional[str] = error
