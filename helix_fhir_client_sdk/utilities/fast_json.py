"""
The one place the SDK chooses how JSON text is read and written.

Call sites depend on this module, not on orjson, so a later vendor change touches one file.
``byte_identical=True`` gives exactly what the standard library wrote before orjson was adopted
(see adrs/0001-faster-json-with-orjson.md).  Functions only, no module state.
"""

import json
import logging
import time
from typing import Any, cast

import orjson
from compressedfhir.utilities.fhir_json_encoder import FhirJSONEncoder
from opentelemetry import trace

logger = logging.getLogger(__name__)

_ENCODER = FhirJSONEncoder()

# datetime and dataclass go through the FhirJSONEncoder hook so their text matches the
# standard library path; orjson's native handling differs (it drops dataclass fields named "_h"
# and rewrites seconds-level UTC offsets).
_DUMPS_OPTIONS = orjson.OPT_PASSTHROUGH_DATETIME | orjson.OPT_PASSTHROUGH_DATACLASS


class JsonDecodeError(json.JSONDecodeError):
    """
    Raised by :func:`loads` for text that cannot be parsed.

    Subclasses ``json.JSONDecodeError`` so existing handlers keep working; the underlying
    orjson error is chained as ``__cause__`` and never escapes the SDK.
    """


def _record(operation: str, size: int, started: float | None, *, fallback: bool = False, error: bool = False) -> None:
    span = trace.get_current_span()
    if not span.is_recording():
        return
    span.set_attribute("json.operation", operation)
    span.set_attribute("json.bytes", size)
    if started is not None:
        span.set_attribute("json.duration_ms", (time.perf_counter() - started) * 1000)
    span.set_attribute("json.fallback", fallback)
    span.set_attribute("json.error", error)


def dumps_str(obj: object, *, byte_identical: bool = False) -> str:
    """
    Serialize ``obj`` to JSON text.

    :param obj: value to serialize
    :param byte_identical: True writes exactly the text the standard library wrote before orjson
        (``json.dumps(obj, cls=FhirJSONEncoder)``).  False (default) writes compact text with
        non-ASCII as raw UTF-8, and NaN / Infinity as ``null``.  Values orjson cannot encode
        (integers beyond 64 bits, non-string keys) fall back to the standard library text.
    :return: JSON text
    """
    started = time.perf_counter()
    if byte_identical:
        text = json.dumps(obj, cls=FhirJSONEncoder)
        _record("dumps", len(text), started)
        return text
    try:
        text = orjson.dumps(obj, default=_ENCODER.default, option=_DUMPS_OPTIONS).decode()
    except TypeError as e:  # orjson.JSONEncodeError subclasses TypeError
        logger.debug("fast_json.dumps_str fell back to the standard library: %s", type(e).__name__)
        text = json.dumps(obj, cls=FhirJSONEncoder)
        _record("dumps", len(text), started, fallback=True)
        return text
    _record("dumps", len(text), started)
    return text


def loads(text: str | bytes, *, byte_identical: bool = False) -> Any:
    """
    Parse JSON text.

    :param text: JSON text
    :param byte_identical: True parses with the standard library (exact big integers, accepts
        NaN / Infinity).  False (default) parses with orjson: an integer outside -2^63..2^64-1
        becomes a float, and NaN / Infinity / ``1e400`` / nesting deeper than 1024 are rejected.
    :return: the parsed value
    :raises JsonDecodeError: when the text cannot be parsed (a ``json.JSONDecodeError``)
    """
    started = time.perf_counter()
    if byte_identical:
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            _record("loads", len(text), started, error=True)
            raise
        _record("loads", len(text), started)
        return value
    try:
        value = orjson.loads(text)
    except orjson.JSONDecodeError as e:
        _record("loads", len(text), started, error=True)
        # orjson's error subclasses json.JSONDecodeError at runtime; its stubs do not say so
        cause = cast(json.JSONDecodeError, e)
        raise JsonDecodeError(cause.msg, cause.doc if isinstance(cause.doc, str) else "", cause.pos) from e
    _record("loads", len(text), started)
    return value
