from typing import Optional


class FhirValidationException(Exception):
    def __init__(
        self,
        request_id: Optional[str],
        url: str,
        json_data: str,
        response_text: Optional[str],
        response_status_code: Optional[int],
        message: str,
    ) -> None:
        """
        Validation Failure

        :param request_id: request id
        :param url: url that was being accessed
        :param json_data: data that was being sent
        :param response_text: response from the FHIR server
        :param response_status_code: status code returned by FHIR server
        :param message: error message"""
        self.request_id: Optional[str] = request_id
        self.url: str = url
        self.data: str = json_data
        super().__init__(
            f"FHIR send  {request_id} validation failed: {url} {response_status_code}: {json_data}.  {message} {response_text}"
        )
