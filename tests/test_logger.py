from typing import Any

from helix_fhir_client_sdk.loggers.fhir_logger import FhirLogger


class TestLogger(FhirLogger):
    def info(self, param: Any) -> None:
        """
        Handle messages at INFO level
        """
        print(param)

    def error(self, param: Any) -> None:
        """
        Handle messages at error level
        """
        print(param)

    def debug(self, param: Any) -> None:
        """
        Handle messages at debug level
        """
        print(param)
