import sys
import traceback
from typing import Any


class FhirSenderException(Exception):
    """
    Custom exception for FHIR sender operations that preserves the original
    exception's call stack and provides detailed error context.
    """

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
        :param headers: HTTP headers used in the request
        :param json_data: Payload data that was being sent
        :param response_text: Response text from the FHIR server
        :param response_status_code: HTTP status code returned
        :param variables: Additional context variables
        :param elapsed_time: Time taken for the request
        """
        # Store all context information as attributes
        self.message = message
        self.request_id = request_id
        self.url = url
        self.headers = headers or {}
        self.json_data = json_data
        self.response_text = response_text
        self.response_status_code = response_status_code
        self.variables = variables or {}
        self.elapsed_time = elapsed_time

        # Preserve the original exception's traceback
        self.original_exception: Exception | None
        if exception:
            self.original_exception = exception
            self.original_traceback = traceback.extract_tb(exception.__traceback__)
        else:
            self.original_exception = None
            self.original_traceback = traceback.extract_tb(sys.exc_info()[2])

        # Construct a comprehensive error message
        error_details = []
        if request_id:
            error_details.append(f"Request ID: {request_id}")
        if url:
            error_details.append(f"URL: {url}")
        if response_status_code:
            error_details.append(f"Status Code: {response_status_code}")

        # Combine the main message with additional details
        full_message = message
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
            error_str.append(f"Details: {str(self.original_exception)}")

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
