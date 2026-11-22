from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry.trace import Span, Status, StatusCode


class SpanErrorStatus:
    """
    Marks a span as failed with the type of the exception only.

    The exception messages of this SDK and of aiohttp contain request URLs, with their path ids and
    query values. So the spans of the SDK start with record_exception=False and
    set_status_on_exception=False, and set their error status with this class.
    """

    @staticmethod
    def set(*, span: Span, exception: BaseException) -> None:
        """
        Sets the status of the span to ERROR, with the type of the exception as the description.

        :param span: the span
        :param exception: the exception that ended the work of the span
        """
        span.set_status(Status(StatusCode.ERROR, description=type(exception).__name__))

    @staticmethod
    @contextmanager
    def on_exception(*, span: Span) -> Iterator[None]:
        """
        Sets the status of the span to ERROR (see set) when the block raises an exception.

        :param span: the span
        """
        try:
            yield
        except Exception as e:
            SpanErrorStatus.set(span=span, exception=e)
            raise
