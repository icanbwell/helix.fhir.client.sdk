import dataclasses
import json
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Any


class FhirJSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)  # type:ignore
        if isinstance(o, Enum):
            return o.value
        if isinstance(o, Decimal):
            # Custom Decimal conversion
            if o == o.to_integral_value():
                # If Decimal is a whole number, return as int
                return int(o)
            else:
                # If Decimal has a non-zero decimal part, return as float
                return float(o)
        if isinstance(o, bytes):
            return o.decode("utf-8")
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if hasattr(o, "to_dict"):
            return o.dict()

        return super().default(o)
