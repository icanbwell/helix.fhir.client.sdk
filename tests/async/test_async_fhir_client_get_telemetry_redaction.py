"""DCON-6540: the HTTP GET span, the 429 warnings and FhirSenderException carry no query values,
resource ids or credentials.

aioresponses mocks the FHIR server. SpanRecorder (tests/span_recorder.py) takes the place of the
OpenTelemetry SDK's InMemorySpanExporter, because this package depends only on opentelemetry-api.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from typing import Any

import pytest
from aiohttp import ClientResponseError, InvalidUrlClientError, RequestInfo, TooManyRedirects
from aioresponses import aioresponses
from multidict import CIMultiDict, CIMultiDictProxy
from opentelemetry.trace import StatusCode
from yarl import URL

from helix_fhir_client_sdk.exceptions.fhir_sender_exception import FhirSenderException
from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.function_types import RefreshTokenResult
from helix_fhir_client_sdk.utilities import retryable_aiohttp_client
from helix_fhir_client_sdk.utilities.retryable_aiohttp_client import RetryableAioHttpClient
from tests.span_recorder import RecordedSpan, SpanRecorder

BASE_URL = "http://fhir.example.test/4_0_0"
SERVER_ADDRESS = "fhir.example.test"
PATIENT_ID = "patient-test-001"
PAGE_CURSOR = "synthetic-page-cursor-0001"
ACCESS_TOKEN = "synthetic-access-token-0001"
REFRESHED_ACCESS_TOKEN = "synthetic-access-token-0002"
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


def _too_many_redirects() -> TooManyRedirects:
    # aiohttp raises this error itself (after too many redirects), with the request headers in request_info
    return TooManyRedirects(
        request_info=RequestInfo(
            url=URL(FIRST_PAGE_URL),
            method="GET",
            headers=CIMultiDictProxy(
                CIMultiDict({"Accept": "application/fhir+json", "Authorization": f"Bearer {ACCESS_TOKEN}"})
            ),
            real_url=URL(FIRST_PAGE_URL),
        ),
        history=(),
    )


@dataclass(frozen=True)
class GetScenario:
    name: str
    # (url, aioresponses arguments), in the order in which the server answers; an "exception" value is
    # a factory, so that each test raises a new exception object
    responses: tuple[tuple[str, dict[str, Any]], ...]
    # one value for each GET span; None when no response arrived
    expected_status_codes: tuple[int | None, ...]
    expected_status_codes_otel: tuple[StatusCode, ...]
    expected_attempts: tuple[int, ...]
    # the type name that an ERROR span has as its status description
    expected_error_type: str | None
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
        expected_status_codes_otel=(StatusCode.UNSET,),
        expected_attempts=(1,),
        expected_error_type=None,
        raises=False,
    ),
    GetScenario(
        name="403",
        responses=((FIRST_PAGE_URL, {"status": 403, "payload": OPERATION_OUTCOME}),),
        expected_status_codes=(403,),
        expected_status_codes_otel=(StatusCode.UNSET,),
        expected_attempts=(1,),
        expected_error_type=None,
        raises=False,
    ),
    GetScenario(
        name="404",
        responses=((FIRST_PAGE_URL, {"status": 404, "payload": OPERATION_OUTCOME}),),
        expected_status_codes=(404,),
        expected_status_codes_otel=(StatusCode.UNSET,),
        expected_attempts=(1,),
        expected_error_type=None,
        raises=False,
    ),
    GetScenario(
        name="429-then-200",
        responses=(
            (FIRST_PAGE_URL, {"status": 429, "headers": {"Retry-After": "0"}}),
            (FIRST_PAGE_URL, {"status": 200, "payload": _bundle()}),
        ),
        expected_status_codes=(429, 200),
        expected_status_codes_otel=(StatusCode.UNSET, StatusCode.UNSET),
        expected_attempts=(1, 2),
        expected_error_type=None,
        raises=False,
    ),
    GetScenario(
        name="500-three-times",
        responses=tuple((FIRST_PAGE_URL, {"status": 500}) for _ in range(3)),
        expected_status_codes=(500, 500, 500),
        expected_status_codes_otel=(StatusCode.ERROR,) * 3,
        expected_attempts=(1, 2, 3),
        expected_error_type="ClientResponseError",
        raises=True,
    ),
    GetScenario(
        name="timeout",
        responses=tuple((FIRST_PAGE_URL, {"exception": TimeoutError}) for _ in range(3)),
        expected_status_codes=(None, None, None),
        expected_status_codes_otel=(StatusCode.ERROR,) * 3,
        expected_attempts=(1, 2, 3),
        expected_error_type="TimeoutError",
        raises=True,
    ),
    GetScenario(
        name="too-many-redirects",
        responses=tuple((FIRST_PAGE_URL, {"exception": _too_many_redirects}) for _ in range(3)),
        expected_status_codes=(None, None, None),
        expected_status_codes_otel=(StatusCode.ERROR,) * 3,
        expected_attempts=(1, 2, 3),
        expected_error_type="TooManyRedirects",
        raises=True,
    ),
    GetScenario(
        name="next-page",
        responses=(
            (FIRST_PAGE_URL, {"status": 200, "payload": _bundle(next_url=NEXT_PAGE_URL)}),
            (NEXT_PAGE_URL, {"status": 200, "payload": _bundle()}),
        ),
        expected_status_codes=(200, 200),
        expected_status_codes_otel=(StatusCode.UNSET, StatusCode.UNSET),
        expected_attempts=(1, 1),
        expected_error_type=None,
        raises=False,
    ),
]


def _register(fhir_server: aioresponses, *, url: str, response: dict[str, Any], method: str = "GET") -> None:
    arguments = dict(response)
    if "exception" in arguments:
        exception_factory: Callable[[], Exception] = arguments["exception"]
        arguments["exception"] = exception_factory()
    fhir_server.add(url, method=method, **arguments)


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


def _leaked_values(span: RecordedSpan) -> list[str]:
    return sorted({value for value in VALUES_THAT_MUST_NOT_LEAK for text in span.recorded_texts() if value in text})


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[scenario.name for scenario in SCENARIOS])
async def test_get_span_has_safe_attributes_and_no_query_values_or_tokens(
    scenario: GetScenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    span_recorder = SpanRecorder()
    monkeypatch.setattr(retryable_aiohttp_client, "TRACER", span_recorder)
    fhir_client = _create_fhir_client()

    # Act
    raised = False
    with aioresponses() as fhir_server:
        for url, response in scenario.responses:
            _register(fhir_server, url=url, response=response)
        try:
            await fhir_client.get_async()
        except FhirSenderException:
            raised = True

    # Assert
    assert raised == scenario.raises
    get_spans = span_recorder.spans_named(HTTP_GET_SPAN_NAME)
    assert [span.attributes.get("fhir.client_sdk.attempt") for span in get_spans] == list(scenario.expected_attempts)
    assert [span.attributes.get(STATUS_CODE_KEY) for span in get_spans] == list(scenario.expected_status_codes)
    assert [span.status.status_code for span in get_spans] == list(scenario.expected_status_codes_otel)
    for span, status_code in zip(get_spans, scenario.expected_status_codes, strict=True):
        expected_keys = SPAN_KEYS_FOR_EVERY_ATTEMPT | ({STATUS_CODE_KEY} if status_code is not None else set())
        assert set(span.attributes) == expected_keys
        assert type(span.attributes["fhir.client_sdk.attempt"]) is int
        if status_code is not None:
            assert type(span.attributes[STATUS_CODE_KEY]) is int
        assert span.attributes["fhir.client_sdk.url"] == URL_TEMPLATE
        assert span.attributes["server.address"] == SERVER_ADDRESS
        assert span.attributes["fhir.client_sdk.resource"] == "Observation"
        expected_description = scenario.expected_error_type if span.status.status_code == StatusCode.ERROR else None
        assert span.status.description == expected_description
        assert span.events == []
        assert _leaked_values(span) == []


RAISING_SCENARIOS = [scenario for scenario in SCENARIOS if scenario.raises]


@pytest.mark.parametrize("scenario", RAISING_SCENARIOS, ids=[scenario.name for scenario in RAISING_SCENARIOS])
async def test_get_exception_has_no_authorization_value(scenario: GetScenario) -> None:
    # Arrange
    fhir_client = _create_fhir_client()

    # Act
    with aioresponses() as fhir_server:
        for url, response in scenario.responses:
            _register(fhir_server, url=url, response=response)
        with pytest.raises(FhirSenderException) as exception_info:
            await fhir_client.get_async()

    # Assert
    exception = exception_info.value
    assert exception.headers["Authorization"] == REDACTED
    assert exception.variables["_id"] == REDACTED
    assert ACCESS_TOKEN not in json.dumps(exception.to_dict(), default=str)
    assert ACCESS_TOKEN not in str(exception)
    assert ACCESS_TOKEN not in repr(exception.original_exception)
    assert ACCESS_TOKEN not in repr(exception.__cause__)


async def _refresh_to_a_new_token(
    url: str | None,
    status_code: int | None,
    current_token: str | None,
    expiry_date: datetime | None,
    retry_count: int | None,
) -> RefreshTokenResult:
    return RefreshTokenResult(access_token=REFRESHED_ACCESS_TOKEN, expiry_date=None, abort_request=False)


@pytest.mark.parametrize(
    "response, refresh_token_function",
    [
        pytest.param({"status": 429}, None, id="429-on-the-last-attempt"),
        pytest.param({"status": 401}, _refresh_to_a_new_token, id="401-after-the-token-refresh"),
        pytest.param({"status": 500}, None, id="retryable-status"),
        pytest.param({"status": 418}, None, id="non-retryable-status"),
        pytest.param({"exception": _too_many_redirects}, None, id="raised-by-aiohttp"),
    ],
)
async def test_client_response_error_has_no_authorization_value(
    response: dict[str, Any], refresh_token_function: Any
) -> None:
    # Arrange
    async with RetryableAioHttpClient(
        retries=0,
        refresh_token_func=refresh_token_function,
        use_data_streaming=False,
        access_token=None,
        access_token_expiry_date=None,
        tracer_request_func=None,
    ) as client:
        with aioresponses() as fhir_server:
            _register(fhir_server, url=FIRST_PAGE_URL, response=response)

            # Act
            with pytest.raises(ClientResponseError) as error_info:
                await client.get(
                    url=FIRST_PAGE_URL,
                    headers={"Accept": "application/fhir+json", "Authorization": f"Bearer {ACCESS_TOKEN}"},
                )

    # Assert: only the credential header is redacted; the rest of the request info stays
    error = error_info.value
    assert [token for token in (ACCESS_TOKEN, REFRESHED_ACCESS_TOKEN) if token in repr(error)] == []
    assert error.request_info.headers["Authorization"] == REDACTED
    assert error.request_info.headers["Accept"] == "application/fhir+json"
    assert str(error.request_info.real_url) == FIRST_PAGE_URL


@pytest.mark.parametrize("url", ["http://[::1/path", "http://host]/x", "https://[bad", "http://[not-an-ip]/x"])
async def test_get_span_for_a_url_that_urlsplit_rejects_keeps_the_aiohttp_error(
    url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: aiohttp rejects these URLs before it opens a connection, so no server is needed
    span_recorder = SpanRecorder()
    monkeypatch.setattr(retryable_aiohttp_client, "TRACER", span_recorder)

    # Act
    async with RetryableAioHttpClient(
        retries=0,
        use_data_streaming=False,
        access_token=None,
        access_token_expiry_date=None,
        refresh_token_func=None,
        tracer_request_func=None,
    ) as client:
        with pytest.raises(InvalidUrlClientError):
            await client.get(url=url, headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})

    # Assert
    [span] = span_recorder.spans_named(HTTP_GET_SPAN_NAME)
    assert span.attributes == {"fhir.client_sdk.url": "{url}", "fhir.client_sdk.attempt": 1}
    assert span.status.status_code == StatusCode.ERROR
    assert span.status.description == "InvalidUrlClientError"


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
