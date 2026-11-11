"""An in-memory span recorder for tests.

It takes the place of the OpenTelemetry SDK's InMemorySpanExporter, because this package depends only on
opentelemetry-api. start_as_current_span activates each span with the API's own use_span, so exceptions
and status are handled as with the SDK tracer.
"""

import traceback
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import INVALID_SPAN_CONTEXT, NonRecordingSpan, Span, Status, StatusCode
from opentelemetry.util import types


class RecordedSpan(NonRecordingSpan):
    """Keeps the attributes, events and status that the code under test records."""

    def __init__(self, *, name: str) -> None:
        super().__init__(INVALID_SPAN_CONTEXT)
        self.name = name
        self.attributes: dict[str, Any] = {}
        self.events: list[tuple[str, dict[str, Any]]] = []
        self.status = Status(StatusCode.UNSET)
        self.ended = False

    def is_recording(self) -> bool:
        return not self.ended

    def set_attribute(self, key: str, value: types.AnyValue) -> None:
        self.attributes[key] = value

    def set_attributes(self, attributes: Mapping[str, types.AnyValue]) -> None:
        self.attributes.update(attributes)

    def add_event(self, name: str, attributes: types.Attributes = None, timestamp: int | None = None) -> None:
        self.events.append((name, dict(attributes or {})))

    def set_status(self, status: Status | StatusCode, description: str | None = None) -> None:
        self.status = status if isinstance(status, Status) else Status(status, description)

    def record_exception(
        self,
        exception: BaseException,
        attributes: types.Attributes = None,
        timestamp: int | None = None,
        escaped: bool = False,
    ) -> None:
        # the same event attributes as Span.record_exception of the OpenTelemetry SDK
        self.add_event(
            "exception",
            {
                "exception.type": type(exception).__name__,
                "exception.message": str(exception),
                "exception.stacktrace": "".join(traceback.format_exception(exception)),
                "exception.escaped": str(escaped),
                **dict(attributes or {}),
            },
        )

    def end(self, end_time: int | None = None) -> None:
        self.ended = True

    def recorded_texts(self) -> list[str]:
        """Returns every value that the span recorded: attributes, event attributes and the status description."""
        texts = [str(value) for value in self.attributes.values()]
        texts += [str(value) for _, attributes in self.events for value in attributes.values()]
        texts.append(self.status.description or "")
        return texts


class SpanRecorder:
    """Takes the place of the module tracer (TRACER) of the code under test and keeps every span it starts."""

    def __init__(self) -> None:
        self.spans: list[RecordedSpan] = []

    def start_span(self, name: str, **_kwargs: Any) -> RecordedSpan:
        span = RecordedSpan(name=name)
        self.spans.append(span)
        return span

    @contextmanager
    def start_as_current_span(
        self,
        name: str,
        *,
        record_exception: bool = True,
        set_status_on_exception: bool = True,
        **_kwargs: Any,
    ) -> Iterator[Span]:
        span = self.start_span(name)
        with trace.use_span(
            span,
            end_on_exit=True,
            record_exception=record_exception,
            set_status_on_exception=set_status_on_exception,
        ) as current_span:
            yield current_span

    def spans_named(self, name: str) -> list[RecordedSpan]:
        return [span for span in self.spans if span.name == name]
