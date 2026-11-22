import json
from logging import Logger
from typing import Any

from helix_fhir_client_sdk.utilities.fast_json import JsonDecodeError, loads


class NdJsonInvalidLineError(JsonDecodeError):
    """
    A newline-terminated NDJSON line is not valid JSON.

    ``parsed`` holds the objects from the lines before it in the same chunk, so a caller can use
    them before it stops the stream.
    """

    def __init__(self, cause: json.JSONDecodeError, parsed: list[dict[str, Any]]) -> None:
        super().__init__(cause.msg, cause.doc if isinstance(cause.doc, str) else "", cause.pos)
        self.parsed: list[dict[str, Any]] = parsed


class NdJsonChunkStreamingParser:
    def __init__(self, *, byte_identical_json: bool = False) -> None:
        # Holds the text after the last newline, which may be the start of a line that has not fully arrived
        self.buffer = ""
        self._byte_identical_json: bool = byte_identical_json

    def add_chunk(self, chunk: str, logger: Logger | None) -> list[dict[str, Any]]:
        """
        Add a new chunk of NDJSON data and return a list of complete JSON objects.

        Only the text after the last newline can be a partial line.  A line that ends in a newline is
        complete, so one that does not parse is an error and is raised, never held back or dropped.

        :param chunk: A string containing a chunk of NDJSON data.
        :param logger: A logger to log errors.
        :return: A list of complete JSON objects extracted from the chunk.
        :raises NdJsonInvalidLineError: when a newline-terminated line is not valid JSON; the objects parsed
            from the lines before it are on the exception's ``parsed``
        """
        lines = (self.buffer + chunk).split("\n")
        # the text after the last newline: empty when the chunk ended on a newline
        pending = lines.pop()

        complete_json_objects: list[dict[str, Any]] = []
        for line in lines:
            if not line.strip():
                continue
            try:
                complete_json_objects.append(loads(line, byte_identical=self._byte_identical_json))
            except json.JSONDecodeError as e:
                # the stream is invalid from here on; the caller decides what to do with the good lines before it
                self.buffer = ""
                raise NdJsonInvalidLineError(e, complete_json_objects) from e

        if pending.strip():
            try:
                # a failure here is expected at a chunk boundary, so it is not recorded as a span error
                complete_json_objects.append(
                    loads(pending, byte_identical=self._byte_identical_json, record_errors=False)
                )
                pending = ""
            except json.JSONDecodeError:
                # the rest of this line may arrive in the next chunk
                pass
        else:
            pending = ""

        self.buffer = pending
        return complete_json_objects
