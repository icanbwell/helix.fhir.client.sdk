import json
from typing import Any

from helix_fhir_client_sdk.utilities.fast_json import loads


def parse_json_or_ndjson(text: str, *, byte_identical: bool = False) -> Any:
    """
    Parses a response body that is normally a single JSON object/array, but may be
    newline-delimited JSON (one object per line) when the caller requested an ndjson
    Accept header (e.g. $merge with use_data_streaming enabled). A single JSON document
    parses on the first attempt unchanged; only a genuine multi-line ndjson body - which
    is not valid as a single JSON document - falls back to per-line parsing.

    :param text: response body to parse
    :param byte_identical: parse with the standard library instead of orjson
    :return: parsed JSON, or a list of parsed JSON objects for a multi-line ndjson body
    """
    try:
        # a multi-line NDJSON body is expected to fail as one document, so do not mark the span as an error
        return loads(text, byte_identical=byte_identical, record_errors=False)
    except json.JSONDecodeError:
        return [loads(line, byte_identical=byte_identical) for line in text.splitlines() if line.strip()]
