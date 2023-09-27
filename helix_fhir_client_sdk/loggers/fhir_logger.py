from typing import Any


class FhirLogger:
    """
    Dummy Logger
    """

    def info(self, param: Any) -> None:
        """
        Handle messages at INFO level
        """

    def error(self, param: Any) -> None:
        """
        Handle messages at error level
        """

    def debug(self, param: Any) -> None:
        """
        Handle messages at debug level
        """
