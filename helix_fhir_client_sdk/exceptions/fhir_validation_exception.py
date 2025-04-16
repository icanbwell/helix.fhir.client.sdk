from typing import Any

from helix_fhir_client_sdk.dictionary_writer import convert_dict_to_str


class FhirValidationException(Exception):
    def __init__(
        self,
        *,
        request_id: str | None,
        url: str,
        json_data: str,
        response_text: str | None,
        response_status_code: int | None,
        message: str,
        headers: dict[str, str],
        issue: list[dict[str, Any]] | None,
    ) -> None:
        """
        Validation Failure


        :param request_id: request id
        :param url: url that was being accessed
        :param json_data: data that was being sent
        :param response_text: response from the FHIR server
        :param response_status_code: status code returned by FHIR server
        :param message: error message
        :param issue: FHIR OperationOutcomeIssue
        """
        self.request_id: str | None = request_id
        self.url: str = url
        self.data: str = json_data
        self.headers = headers
        self.issue: list[dict[str, Any]] | None = issue
        json = {
            "message": f"FHIR validation failed: {message}",
            "request_id": request_id,
            "url": url,
            "status_code": response_status_code,
            "headers": headers,
            "response_text": response_text,
            "json_data": json_data,
            "issue": issue,
        }

        super().__init__(convert_dict_to_str(json))
