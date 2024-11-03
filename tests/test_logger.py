import logging
from logging import Logger
from typing import Any

from helix_fhir_client_sdk.loggers.fhir_logger import FhirLogger


class TestLogger(FhirLogger):
    def __init__(self) -> None:
        self.logger: Logger = Logger("FhirLogger")
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(module)s.%(funcName)s[%(lineno)d]: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG)

    def info(self, param: Any) -> None:
        """
        Handle messages at INFO level
        """
        self.logger.info(param)

    def error(self, param: Any) -> None:
        """
        Handle messages at error level
        """
        self.logger.error(param)

    def debug(self, param: Any) -> None:
        """
        Handle messages at debug level
        """
        self.logger.debug(param)
