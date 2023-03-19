import traceback
from typing import Optional, Dict, Any

from helix_fhir_client_sdk.dictionary_writer import convert_dict_to_str


class FhirSenderException(Exception):
    def __init__(
        self,
        request_id: Optional[str],
        exception: Exception,
        url: str,
        headers: Dict[str, str],
        json_data: str,
        response_text: Optional[str],
        response_status_code: Optional[int],
        message: str,
        variables: Dict[str, Any],
        elapsed_time: float,
    ) -> None:
        """
        Creates an exception when sending data

        :param request_id: request id
        :param exception: Exception thrown
        :param url: url that was being accessed
        :param json_data: data that was being sent
        :param response_text: response from the FHIR server
        :param response_status_code: status code returned by FHIR server
        :param message: error message
        """
        self.request_id: Optional[str] = request_id
        self.exception: Exception = exception
        self.url: str = url
        self.data: str = json_data
        self.headers = headers
        self.variables: Dict[str, Any] = variables
        self.elapsed_time: float = elapsed_time
        self.response_text: Optional[str] = response_text
        self.response_status_code: Optional[int] = response_status_code
        json = {
            "message": f"FHIR send failed: {message}",
            "request_id": request_id,
            "url": url,
            "status_code": response_status_code,
            "headers": headers,
            "variables": variables,
            "elapsed_time": elapsed_time,
            "response_text": response_text,
            "json_data": json_data,
            "exception": "".join(
                traceback.TracebackException.from_exception(exception).format()
            ),
        }

        super().__init__(convert_dict_to_str(json))
