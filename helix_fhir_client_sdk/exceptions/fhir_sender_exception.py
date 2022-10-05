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
        super().__init__(
            f"FHIR send {request_id} failed to {url} {response_status_code}: {json_data}.  {message} {response_text}. "
            + f"headers={convert_dict_to_str(headers)}, "
            + f"variables={convert_dict_to_str(variables)}, "
            + f"elapsed time in seconds={elapsed_time}"
        )
