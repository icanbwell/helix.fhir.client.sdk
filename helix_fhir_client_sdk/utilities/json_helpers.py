import json
from typing import Any


def parse_json_or_ndjson(text: str) -> Any:
    """
    Parses a response body that is normally a single JSON object/array, but may be
    newline-delimited JSON (one object per line) when the caller requested an ndjson
    Accept header (e.g. $merge with use_data_streaming enabled). A single JSON document
    parses on the first attempt unchanged; only a genuine multi-line ndjson body - which
    is not valid as a single JSON document - falls back to per-line parsing.

    :param text: response body to parse
    :return: parsed JSON, or a list of parsed JSON objects for a multi-line ndjson body
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]
