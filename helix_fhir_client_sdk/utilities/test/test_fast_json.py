import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import orjson
import pytest
from compressedfhir.utilities.fhir_json_encoder import FhirJSONEncoder

from helix_fhir_client_sdk.utilities.fast_json import JsonDecodeError, dumps_str, loads

# Synthetic data only (no PHI).
BIG_INT_TEXT = "1" + "0" * 29


class _FakeSpan:
    def __init__(self) -> None:
        self.attributes: dict[str, Any] = {}

    def is_recording(self) -> bool:
        return True

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value


@dataclass
class _WithUnderscoreField:
    _h: int
    name: str


@pytest.mark.parametrize(
    "value",
    [
        {"a": 1, "b": [1, 2, {"c": "d"}]},
        {"name": "Zoë Ångström 日本語"},
        {"text": "line separator and \u0085 next-line"},
        {"floats": [0.1, 1e-7, 1.5e300, -0.0]},
        {"amount": Decimal("12.50"), "count": Decimal("3")},
        {"when": datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)},
        {"when": datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=5, minutes=30, seconds=15)))},
        {"data": _WithUnderscoreField(_h=1, name="x")},
        {"path": Path("some/relative/x"), "raw": b"bytes"},
    ],
)
def test_byte_identical_dumps_matches_legacy_encoder(value: Any) -> None:
    assert dumps_str(value, byte_identical=True) == json.dumps(value, cls=FhirJSONEncoder)


@pytest.mark.parametrize(
    "value",
    [
        {"a": 1, "b": [1, 2, {"c": "d"}]},
        {"name": "Zoë Ångström 日本語"},
        {"text": "line separator and \u0085 next-line"},
        {"floats": [0.1, 1e-7, 1.5e300]},
        {"amount": Decimal("12.50"), "count": Decimal("3")},
        {"when": datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)},
        {"when": datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=5, minutes=30, seconds=15)))},
        {"data": _WithUnderscoreField(_h=1, name="x")},
        {"path": Path("some/relative/x"), "raw": b"bytes"},
    ],
)
def test_default_dumps_parses_to_same_value_as_legacy_encoder(value: Any) -> None:
    default_text = dumps_str(value)
    legacy_text = json.dumps(value, cls=FhirJSONEncoder)

    assert json.loads(default_text) == json.loads(legacy_text)


def test_default_dumps_is_compact_raw_utf8() -> None:
    text = dumps_str({"a": [1, 2], "n": "é"})

    assert text == '{"a":[1,2],"n":"é"}'


@pytest.mark.parametrize(
    "value, expected",
    [
        ({"x": float("nan")}, '{"x":null}'),
        ({"x": float("inf")}, '{"x":null}'),
    ],
)
def test_default_dumps_writes_non_finite_as_null(value: dict[str, float], expected: str) -> None:
    assert dumps_str(value) == expected


def test_byte_identical_dumps_keeps_stdlib_non_finite_literal() -> None:
    assert dumps_str({"x": float("nan")}, byte_identical=True) == '{"x": NaN}'


@pytest.mark.parametrize(
    "value",
    [
        {"big": 2**70},
        {1: "int key"},
    ],
)
def test_default_dumps_falls_back_to_stdlib_when_orjson_cannot_encode(value: Any) -> None:
    assert dumps_str(value) == json.dumps(value, cls=FhirJSONEncoder)


def test_dataclass_underscore_field_is_not_dropped() -> None:
    text = dumps_str({"data": _WithUnderscoreField(_h=7, name="x")})

    assert json.loads(text) == {"data": {"_h": 7, "name": "x"}}


def test_datetime_with_seconds_offset_is_written_like_the_legacy_encoder() -> None:
    value = {"when": datetime(2024, 1, 2, tzinfo=timezone(timedelta(hours=5, minutes=30, seconds=15)))}

    assert dumps_str(value) == json.dumps(value, cls=FhirJSONEncoder, separators=(",", ":"))


@pytest.mark.parametrize("payload", ['{"a": 1}', b'{"a": 1}'])
@pytest.mark.parametrize("byte_identical", [False, True])
def test_loads_accepts_str_and_bytes(payload: str | bytes, byte_identical: bool) -> None:
    assert loads(payload, byte_identical=byte_identical) == {"a": 1}


def test_loads_default_turns_a_huge_integer_into_a_float() -> None:
    assert isinstance(loads(BIG_INT_TEXT), float)


def test_loads_byte_identical_keeps_a_huge_integer_exact() -> None:
    assert loads(BIG_INT_TEXT, byte_identical=True) == int(BIG_INT_TEXT)


@pytest.mark.parametrize("payload", ["[1, 2,]", "", "{bad", '{"a": 1'])
def test_loads_default_rejects_invalid_json_with_sdk_error_that_is_a_json_decode_error(payload: str) -> None:
    with pytest.raises(JsonDecodeError) as exc_info:
        loads(payload)

    assert isinstance(exc_info.value, json.JSONDecodeError)
    assert isinstance(exc_info.value.__cause__, orjson.JSONDecodeError)


@pytest.mark.parametrize("payload", ["NaN", "Infinity", "-Infinity", "1e400", '"\\ud800"', '{"a": [NaN, 1e400]}'])
def test_loads_default_falls_back_to_stdlib_for_text_only_stdlib_accepts(payload: str) -> None:
    with pytest.raises(orjson.JSONDecodeError):
        orjson.loads(payload)

    assert repr(loads(payload)) == repr(json.loads(payload))


def test_loads_default_fallback_is_recorded_on_the_span(monkeypatch: pytest.MonkeyPatch) -> None:
    span = _FakeSpan()
    monkeypatch.setattr("helix_fhir_client_sdk.utilities.fast_json.trace.get_current_span", lambda: span)

    loads("[NaN]")

    assert span.attributes["json.fallback"] is True
    assert "json.error" not in span.attributes


def test_loads_deeply_nested_input_never_leaks_a_recursion_error() -> None:
    nested = "[" * 1100 + "]" * 1100

    # orjson rejects this; the stdlib accepts it on some Python versions and hits its recursion limit on others
    try:
        loads(nested)
    except JsonDecodeError:
        pass


@pytest.mark.parametrize(
    "payload",
    ["[1, 2.5, -3, 1e2, 0.1]", '{"a": {"b": [true, false, null]}}', '"text"'],
)
def test_loads_ordinary_values_are_equal_in_both_modes(payload: str) -> None:
    assert loads(payload) == loads(payload, byte_identical=True)


def test_loads_error_type_exposed_to_callers_is_not_an_orjson_type() -> None:
    with pytest.raises(json.JSONDecodeError) as exc_info:
        loads("{bad")

    assert type(exc_info.value) is JsonDecodeError


@pytest.mark.parametrize("byte_identical", [False, True])
def test_loads_raises_the_sdk_error_in_both_modes(byte_identical: bool) -> None:
    with pytest.raises(JsonDecodeError):
        loads("{bad", byte_identical=byte_identical)


def test_span_attributes_do_not_let_a_later_success_hide_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    span = _FakeSpan()
    monkeypatch.setattr("helix_fhir_client_sdk.utilities.fast_json.trace.get_current_span", lambda: span)

    with pytest.raises(JsonDecodeError):
        loads("{bad")
    loads('{"ok": true}')

    assert span.attributes["json.error"] is True
    assert span.attributes["json.chars"] == len('{"ok": true}')
    assert "json.bytes" not in span.attributes
    assert all(not isinstance(v, str) or v in {"loads"} for v in span.attributes.values())


def test_expected_failure_is_not_recorded_as_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    span = _FakeSpan()
    monkeypatch.setattr("helix_fhir_client_sdk.utilities.fast_json.trace.get_current_span", lambda: span)

    with pytest.raises(JsonDecodeError):
        loads("{bad", record_errors=False)

    assert "json.error" not in span.attributes


@pytest.mark.parametrize("byte_identical", [False, True])
@pytest.mark.parametrize("payload", [b'{"a": "\xff"}', b"\xff\xfe", b'{"a": "\xc3"}'])
def test_loads_invalid_utf8_bytes_raise_the_sdk_error(payload: bytes, byte_identical: bool) -> None:
    with pytest.raises(JsonDecodeError):
        loads(payload, byte_identical=byte_identical)
