from typing import Optional


class FhirValidationException(Exception):
    def __init__(
        self,
        url: str,
        json_data: str,
        response_text: Optional[str],
        response_status_code: Optional[int],
        message: str,
    ) -> None:
        self.url: str = url
        self.data: str = json_data
        super().__init__(
            f"FHIR send validation failed: {url} {response_status_code}: {json_data}.  {message} {response_text}"
        )
