import dataclasses


@dataclasses.dataclass
class RetryableAioHttpUrlResult:
    ok: bool
    url: str
    status_code: int
    retry_count: int
    start_time: float
    end_time: float
