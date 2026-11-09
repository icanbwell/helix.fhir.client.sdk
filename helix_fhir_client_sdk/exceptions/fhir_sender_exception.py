import sys
import traceback
from collections.abc import Mapping
from typing import Any

from helix_fhir_client_sdk.utilities.header_redactor import HeaderRedactor
from helix_fhir_client_sdk.utilities.url_redactor import UrlRedactor


class FhirSenderException(Exception):
    """
    Custom exception for FHIR sender operations that preserves the original
    exception's call stack and provides detailed error context.

    The exception keeps redacted copies of the request headers and of the variables:
    credentials and identifiers do not go into it. Its message (str) shows URL templates
    (see UrlRedactor); the url attribute keeps the raw URL, which must not be logged.
    """

    # variables of the FHIR client that carry resource ids or search values
    _IDENTIFIER_VARIABLE_NAMES: frozenset[str] = frozenset({"_id", "_obj_id", "_additional_parameters", "_filters"})
    # variables of the FHIR client that hold request headers
    _HEADER_VARIABLE_NAMES: frozenset[str] = frozenset({"_additional_request_headers"})

    def __init__(
        self,
        message: str,
        exception: Exception | None = None,
        request_id: str | None = None,
        url: str | None = None,
        headers: dict[str, str] | None = None,
        json_data: str | None = None,
        response_text: str | None = None,
        response_status_code: int | None = None,
        variables: dict[str, Any] | None = None,
        elapsed_time: float | None = None,
    ) -> None:
        """
        Initialize the FHIR sender exception with comprehensive error details.

        :param message: Primary error message
        :param exception: The original exception that was caught
        :param request_id: Unique identifier for the request
        :param url: URL that was being accessed
        :param headers: HTTP headers used in the request; the exception keeps a copy with the
                        credential values redacted
        :param json_data: Payload data that was being sent
        :param response_text: Response text from the FHIR server
        :param response_status_code: HTTP status code returned
        :param variables: Additional context variables; the exception keeps a copy with the
                          identifier values and credential headers redacted
        :param elapsed_time: Time taken for the request
        """
        # Store all context information as attributes
        self.message = message
        self.request_id = request_id
        self.url = url
        # a copy: the request code writes the bearer token of the next request into the headers dict
        self.headers = HeaderRedactor.redact(headers=headers)
        self.json_data = json_data
        self.response_text = response_text
        self.response_status_code = response_status_code
        self.variables = self._redact_variables(variables)
        self.elapsed_time = elapsed_time

        # Preserve the original exception's traceback
        self.original_exception: Exception | None
        if exception:
            self.original_exception = exception
            self.original_traceback = traceback.extract_tb(exception.__traceback__)
        else:
            self.original_exception = None
            self.original_traceback = traceback.extract_tb(sys.exc_info()[2])

        # Construct a comprehensive error message, with URL templates: the raw URLs can carry patient
        # identifiers and tokens in their paths and queries
        error_details = []
        if request_id:
            error_details.append(f"Request ID: {request_id}")
        if url:
            error_details.append(f"URL: {UrlRedactor.get_url_template(url=url)}")
        if response_status_code:
            error_details.append(f"Status Code: {response_status_code}")

        # Combine the main message with additional details
        full_message = UrlRedactor.replace_urls_with_templates(text=message)
        if error_details:
            full_message += " | " + " | ".join(error_details)

        # Call the parent class constructor with the full message
        super().__init__(full_message)

    def __str__(self) -> str:
        """
        Custom string representation of the exception.

        :return: Detailed error message with traceback
        """
        # Start with the exception message
        error_str: list[str] = [super().__str__()]

        # Add original exception details if available
        if self.original_exception:
            error_str.append("\nOriginal Exception:")
            error_str.append(f"Type: {type(self.original_exception).__name__}")
            # aiohttp and requests put the full request URL in their exception messages
            error_str.append(f"Details: {UrlRedactor.replace_urls_with_templates(text=str(self.original_exception))}")

        # Add traceback information
        error_str.append("\nTraceback:")
        error_str.extend(traceback.format_list(self.original_traceback))

        return "\n".join(error_str)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert exception details to a dictionary for logging or serialization.

        :return: Dictionary representation of the exception
        """
        return {
            "message": self.message,
            "request_id": self.request_id,
            "url": self.url,
            "status_code": self.response_status_code,
            "headers": self.headers,
            "json_data": self.json_data,
            "response_text": self.response_text,
            "variables": self.variables,
            "elapsed_time": self.elapsed_time,
            "exception_type": (type(self.original_exception).__name__ if self.original_exception else None),
            "exception_details": (str(self.original_exception) if self.original_exception else None),
        }

    @classmethod
    def _redact_variables(cls, variables: Mapping[str, Any] | None) -> dict[str, Any]:
        """
        Returns a copy of the variables in which the identifier values and the credential headers
        are redacted. An empty value carries no identifier, so it stays as it is.

        :param variables: the variables of the FHIR client
        :return: the redacted copy
        """
        redacted_variables: dict[str, Any] = {}
        for name, value in (variables or {}).items():
            if name in cls._IDENTIFIER_VARIABLE_NAMES and value:
                redacted_variables[name] = HeaderRedactor.REDACTED
            elif name in cls._HEADER_VARIABLE_NAMES and isinstance(value, Mapping):
                redacted_variables[name] = HeaderRedactor.redact(headers=value)
            else:
                redacted_variables[name] = value
        return redacted_variables
