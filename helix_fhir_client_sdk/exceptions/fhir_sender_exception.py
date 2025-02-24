from copy import deepcopy
import traceback
from typing import Optional, Dict, Any

from helix_fhir_client_sdk.dictionary_writer import convert_dict_to_str
from helix_fhir_client_sdk.utilities.json_helpers import FhirClientJsonHelpers


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
        # Hide sensitive tokens to protect against unauthorized access
        headers_to_log = deepcopy(self.headers)
        if headers_to_log.get("Authorization"):
            headers_to_log["Authorization"] = "[FILTERED]"
        variables_to_log = deepcopy(self.variables)
        if isinstance(variables, Dict):
            FhirClientJsonHelpers.get_variables_to_log(variables_to_log)
        json = {
            "message": f"FHIR send failed: {message}",
            "request_id": request_id,
            "url": url,
            "status_code": response_status_code,
            "headers": headers,
            "variables": variables_to_log,
            "elapsed_time": elapsed_time,
            "response_text": response_text,
            "json_data": (
                "[FILTERED]" if self.data else ""
            ),  # Hide and protect sensitive JSON data
            "exception": "".join(
                traceback.TracebackException.from_exception(exception).format()
            ),
        }

        super().__init__(convert_dict_to_str(json))
