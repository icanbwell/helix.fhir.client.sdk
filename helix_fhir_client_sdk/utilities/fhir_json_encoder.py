import dataclasses
import json
from datetime import datetime, date
from enum import Enum
from typing import Any


class FhirJSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        if isinstance(o, Enum):
            return o.value
        if isinstance(o, (datetime, date)):
            return o.isoformat().replace("+00:00", ".000Z")
        if hasattr(o, "to_dict"):
            return o.to_dict()
        return super().default(o)
