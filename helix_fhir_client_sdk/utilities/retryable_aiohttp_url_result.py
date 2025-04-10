import dataclasses
from typing import Dict, Any


@dataclasses.dataclass(slots=True)
class RetryableAioHttpUrlResult:
    ok: bool
    url: str
    status_code: int
    retry_count: int
    start_time: float
    end_time: float

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the object to a dictionary

        :return: dictionary
        """
        return {
            "ok": self.ok,
            "url": self.url,
            "status_code": self.status_code,
            "retry_count": self.retry_count,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }
