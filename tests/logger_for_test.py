import logging
from collections.abc import Mapping
from logging import Logger
from typing import Any


class LoggerForTest(Logger):
    def __init__(self, name: str = "Logger") -> None:
        super().__init__(name)
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(module)s.%(funcName)s[%(lineno)d]: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        super().addHandler(handler)
        super().setLevel(logging.DEBUG)

    def info(
        self,
        msg: object,
        *args: object,
        exc_info: Any = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, object] | None = None,
    ) -> None:
        """
        Handle messages at INFO level
        """
        super().info(msg)

    def error(
        self,
        msg: object,
        *args: object,
        exc_info: Any = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, object] | None = None,
    ) -> None:
        """
        Handle messages at error level
        """
        super().error(msg)

    def debug(
        self,
        msg: object,
        *args: object,
        exc_info: Any = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, object] | None = None,
    ) -> None:
        """
        Handle messages at debug level
        """
        super().debug(msg)
