"""DCON-6540: the HTTP GET span, the 429 warnings and FhirSenderException carry no query values,
resource ids or credentials.

aioresponses mocks the FHIR server. _SpanRecorder takes the place of the OpenTelemetry SDK's
InMemorySpanExporter, because this package depends only on opentelemetry-api. It activates each span
with the API's own use_span, so exceptions and status are handled as with the SDK tracer.
"""

import asyncio
import json
import logging
import traceback
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from typing import Any

import pytest
from aioresponses import aioresponses
from opentelemetry import trace
from opentelemetry.trace import INVALID_SPAN_CONTEXT, NonRecordingSpan, Span, Status, StatusCode
from opentelemetry.util import types

from helix_fhir_client_sdk.exceptions.fhir_sender_exception import FhirSenderException
from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.utilities import retryable_aiohttp_client
from helix_fhir_client_sdk.utilities.retryable_aiohttp_client import RetryableAioHttpClient

BASE_URL = "http://fhir.example.test/4_0_0"
SERVER_ADDRESS = "fhir.example.test"
PATIENT_ID = "patient-test-001"
PAGE_CURSOR = "synthetic-page-cursor-0001"
ACCESS_TOKEN = "synthetic-access-token-0001"
REDACTED = "[REDACTED]"
FIRST_PAGE_URL = f"{BASE_URL}/Observation?patient={PATIENT_ID}"
NEXT_PAGE_URL = f"{BASE_URL}/Observation?_getpages={PAGE_CURSOR}&_getpagesoffset=10&_count=10"
URL_TEMPLATE = f"{BASE_URL}/Observation"
VALUES_THAT_MUST_NOT_LEAK = (PATIENT_ID, PAGE_CURSOR, ACCESS_TOKEN, "?")
HTTP_GET_SPAN_NAME = "fhir.client_sdk.http.get"
SPAN_KEYS_FOR_EVERY_ATTEMPT = {
    "fhir.client_sdk.url",
    "fhir.client_sdk.resource",
    "server.address",
    "fhir.client_sdk.attempt",
}
STATUS_CODE_KEY = "http.response.status_code"
OPERATION_OUTCOME = {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "forbidden"}]}


class _RecordedSpan(NonRecordingSpan):
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


class _SpanRecorder:
    """Takes the place of the module tracer of retryable_aiohttp_client and keeps every span it starts."""

    def __init__(self) -> None:
        self.spans: list[_RecordedSpan] = []

    @contextmanager
    def start_as_current_span(
        self,
        name: str,
        *,
        record_exception: bool = True,
        set_status_on_exception: bool = True,
        **_kwargs: Any,
    ) -> Iterator[Span]:
        span = _RecordedSpan(name=name)
        self.spans.append(span)
        with trace.use_span(
            span,
            end_on_exit=True,
            record_exception=record_exception,
            set_status_on_exception=set_status_on_exception,
        ) as current_span:
            yield current_span


@dataclass(frozen=True)
class GetScenario:
    name: str
    # (url, aioresponses arguments), in the order in which the server answers
    responses: tuple[tuple[str, dict[str, Any]], ...]
    # one value for each GET span; None when no response arrived
    expected_status_codes: tuple[int | None, ...]
    expected_attempts: tuple[int, ...]
    raises: bool


def _bundle(*, next_url: str | None = None) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [{"resource": {"resourceType": "Observation", "id": "observation-test-001"}}],
    }
    if next_url:
        bundle["link"] = [{"relation": "next", "url": next_url}]
    return bundle


SCENARIOS = [
    GetScenario(
        name="200",
        responses=((FIRST_PAGE_URL, {"status": 200, "payload": _bundle()}),),
        expected_status_codes=(200,),
        expected_attempts=(1,),
        raises=False,
    ),
    GetScenario(
        name="403",
        responses=((FIRST_PAGE_URL, {"status": 403, "payload": OPERATION_OUTCOME}),),
        expected_status_codes=(403,),
        expected_attempts=(1,),
        raises=False,
    ),
    GetScenario(
        name="404",
        responses=((FIRST_PAGE_URL, {"status": 404, "payload": OPERATION_OUTCOME}),),
        expected_status_codes=(404,),
        expected_attempts=(1,),
        raises=False,
    ),
    GetScenario(
        name="429-then-200",
        responses=(
            (FIRST_PAGE_URL, {"status": 429, "headers": {"Retry-After": "0"}}),
            (FIRST_PAGE_URL, {"status": 200, "payload": _bundle()}),
        ),
        expected_status_codes=(429, 200),
        expected_attempts=(1, 2),
        raises=False,
    ),
    GetScenario(
        name="500-three-times",
        responses=tuple((FIRST_PAGE_URL, {"status": 500}) for _ in range(3)),
        expected_status_codes=(500, 500, 500),
        expected_attempts=(1, 2, 3),
        raises=True,
    ),
    GetScenario(
        name="timeout",
        responses=tuple((FIRST_PAGE_URL, {"exception": TimeoutError()}) for _ in range(3)),
        expected_status_codes=(None, None, None),
        expected_attempts=(1, 2, 3),
        raises=True,
    ),
    GetScenario(
        name="next-page",
        responses=(
            (FIRST_PAGE_URL, {"status": 200, "payload": _bundle(next_url=NEXT_PAGE_URL)}),
            (NEXT_PAGE_URL, {"status": 200, "payload": _bundle()}),
        ),
        expected_status_codes=(200, 200),
        expected_attempts=(1, 1),
        raises=False,
    ),
]


def _create_fhir_client() -> FhirClient:
    # GET Observation?patient=<id> with a bearer token; the default retry count gives three attempts
    return (
        FhirClient()
        .url(BASE_URL)
        .resource("Observation")
        .filter_by_resource("Patient")
        .id_(PATIENT_ID)
        .set_access_token(ACCESS_TOKEN)
    )


def _leaked_values(span: _RecordedSpan) -> list[str]:
    recorded_texts = [str(value) for value in span.attributes.values()]
    recorded_texts += [str(value) for _, attributes in span.events for value in attributes.values()]
    recorded_texts.append(span.status.description or "")
    return sorted({value for value in VALUES_THAT_MUST_NOT_LEAK for text in recorded_texts if value in text})


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[scenario.name for scenario in SCENARIOS])
async def test_get_span_has_safe_attributes_and_no_query_values_or_tokens(
    scenario: GetScenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    span_recorder = _SpanRecorder()
    monkeypatch.setattr(retryable_aiohttp_client, "TRACER", span_recorder)
    fhir_client = _create_fhir_client()

    # Act
    raised = False
    with aioresponses() as fhir_server:
        for url, response in scenario.responses:
            fhir_server.get(url, **response)
        try:
            await fhir_client.get_async()
        except FhirSenderException:
            raised = True

    # Assert
    assert raised == scenario.raises
    get_spans = [span for span in span_recorder.spans if span.name == HTTP_GET_SPAN_NAME]
    assert [span.attributes.get("fhir.client_sdk.attempt") for span in get_spans] == list(scenario.expected_attempts)
    assert [span.attributes.get(STATUS_CODE_KEY) for span in get_spans] == list(scenario.expected_status_codes)
    for span, status_code in zip(get_spans, scenario.expected_status_codes, strict=True):
        expected_keys = SPAN_KEYS_FOR_EVERY_ATTEMPT | ({STATUS_CODE_KEY} if status_code is not None else set())
        assert set(span.attributes) == expected_keys
        assert span.attributes["fhir.client_sdk.url"] == URL_TEMPLATE
        assert span.attributes["server.address"] == SERVER_ADDRESS
        assert span.attributes["fhir.client_sdk.resource"] == "Observation"
        assert _leaked_values(span) == []


RAISING_SCENARIOS = [scenario for scenario in SCENARIOS if scenario.raises]


@pytest.mark.parametrize("scenario", RAISING_SCENARIOS, ids=[scenario.name for scenario in RAISING_SCENARIOS])
async def test_get_exception_has_no_authorization_value(scenario: GetScenario) -> None:
    # Arrange
    fhir_client = _create_fhir_client()

    # Act
    with aioresponses() as fhir_server:
        for url, response in scenario.responses:
            fhir_server.get(url, **response)
        with pytest.raises(FhirSenderException) as exception_info:
            await fhir_client.get_async()

    # Assert
    exception = exception_info.value
    assert exception.headers["Authorization"] == REDACTED
    assert exception.variables["_id"] == REDACTED
    assert ACCESS_TOKEN not in json.dumps(exception.to_dict(), default=str)
    assert ACCESS_TOKEN not in str(exception)


def _http_date(*, seconds_from_now: int) -> str:
    return format_datetime(datetime.now(UTC) + timedelta(seconds=seconds_from_now), usegmt=True)


@pytest.mark.parametrize(
    "retry_after_headers",
    [
        pytest.param({"Retry-After": "0"}, id="seconds"),
        pytest.param({"Retry-After": _http_date(seconds_from_now=-60)}, id="date-in-the-past"),
        pytest.param({"Retry-After": _http_date(seconds_from_now=30)}, id="date-in-the-future"),
        pytest.param({"Retry-After": "not-a-date"}, id="unparsable"),
        pytest.param({}, id="missing"),
    ],
)
async def test_429_warning_logs_only_the_host(
    retry_after_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Arrange: the clock is an external boundary; the 60 s and Retry-After waits must not slow the test
    real_sleep = asyncio.sleep

    async def sleep_without_waiting(delay: float, *args: Any, **kwargs: Any) -> None:
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", sleep_without_waiting)
    caplog.set_level(logging.WARNING, logger=retryable_aiohttp_client.logger.name)

    # Act
    async with RetryableAioHttpClient(
        retries=1,
        use_data_streaming=False,
        access_token=None,
        access_token_expiry_date=None,
        refresh_token_func=None,
        tracer_request_func=None,
    ) as client:
        with aioresponses() as fhir_server:
            fhir_server.get(FIRST_PAGE_URL, status=429, headers=retry_after_headers)
            fhir_server.get(FIRST_PAGE_URL, status=200, payload=_bundle())
            response = await client.get(url=FIRST_PAGE_URL, headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})

    # Assert
    warnings = [record.getMessage() for record in caplog.records if record.name == retryable_aiohttp_client.logger.name]
    assert response.status == 200
    assert len(warnings) == 1
    assert f"Received 429 (Too Many Requests) for {SERVER_ADDRESS}." in warnings[0]
    assert [value for value in (*VALUES_THAT_MUST_NOT_LEAK, "/Observation") if value in warnings[0]] == []
