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
        return self.__dict__
