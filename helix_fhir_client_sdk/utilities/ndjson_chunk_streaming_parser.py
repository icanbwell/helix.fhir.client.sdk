import json
from logging import Logger
from typing import Any

from helix_fhir_client_sdk.utilities.fast_json import loads


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
        :raises json.JSONDecodeError: when a newline-terminated line is not valid JSON
        """
        lines = (self.buffer + chunk).split("\n")
        # the text after the last newline: empty when the chunk ended on a newline
        pending = lines.pop()

        complete_json_objects: list[dict[str, Any]] = [
            loads(line, byte_identical=self._byte_identical_json) for line in lines if line.strip()
        ]

        if pending.strip():
            try:
                complete_json_objects.append(loads(pending, byte_identical=self._byte_identical_json))
                pending = ""
            except json.JSONDecodeError:
                # the rest of this line may arrive in the next chunk
                pass
        else:
            pending = ""

        self.buffer = pending
        return complete_json_objects
