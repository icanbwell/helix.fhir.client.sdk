import json
from typing import List, Dict, Any, Optional

from logging import Logger


class NdJsonChunkStreamingParser:
    def __init__(self) -> None:
        # Initialize an empty buffer to store incomplete JSON objects
        self.buffer = ""

    def add_chunk(self, chunk: str, logger: Optional[Logger]) -> List[Dict[str, Any]]:
        """
        Add a new chunk of NDJSON data and return a list of complete JSON objects.

        :param chunk: A string containing a chunk of NDJSON data.
        :param logger: A logger to log errors.
        :return: A list of complete JSON objects extracted from the chunk.
        """
        # if logger:
        #     logger.debug(f"NdJsonChunkStreamingParser: chunk:\n{chunk}")

        # Add the new chunk to the buffer
        self.buffer += chunk
        # Split the buffer into lines based on newline characters
        lines = self.buffer.split("\n")

        complete_json_objects: List[Dict[str, Any]] = []

        incomplete_lines: List[str] = []

        # Process all complete lines
        for line in lines:
            if line.strip():  # Ensure line is not empty
                try:
                    json_object = json.loads(line)  # Load the JSON object
                    complete_json_objects.append(json_object)
                except json.JSONDecodeError as e:
                    incomplete_lines.append(line)
                    # if logger:
                    #     logger.debug(
                    #         f"NdJsonChunkStreamingParser Error parsing line: {line}\nError: {e}."
                    #         "  Will wait for next chunk to see if it fixes the issue."
                    #         f"\nline: {line}"
                    #         f"\nincomplete_lines: {incomplete_lines}"
                    #     )

        # Update the buffer with incomplete lines
        self.buffer = "\n".join(incomplete_lines)
        # Return the list of complete JSON objects
        return complete_json_objects
