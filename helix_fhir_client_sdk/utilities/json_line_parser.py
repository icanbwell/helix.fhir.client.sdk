import json
from typing import Optional, Dict, Any, cast


class JsonLineParser:
    def __init__(self) -> None:
        self.buffer: str = ""
        self.open_braces: int = 0
        self.close_braces: int = 0

    def add_line(self, line: str) -> Optional[Dict[str, Any]]:
        self.buffer += line.strip()
        self.open_braces += line.count("{")
        self.close_braces += line.count("}")

        if self.open_braces > 0 and self.open_braces == self.close_braces:
            try:
                json_obj = cast(Dict[str, Any], json.loads(self.buffer))
                self.buffer = ""
                self.open_braces = 0
                self.close_braces = 0
                return json_obj
            except json.JSONDecodeError:
                print(f"Invalid JSON structure: {self.buffer}")
                self.buffer = ""
                self.open_braces = 0
                self.close_braces = 0
        return None
