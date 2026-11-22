def ndjson_lines(body: str) -> list[str]:
    """Split an NDJSON body on "\\n" only, dropping empty lines.

    str.splitlines() also splits on U+2028, U+2029 and U+0085, which can appear raw
    inside JSON string values and are not NDJSON record separators (BAI-1965).
    """
    return [line for line in body.split("\n") if line]
