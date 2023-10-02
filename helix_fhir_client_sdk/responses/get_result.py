import dataclasses
from typing import List, Dict, Any, Optional


@dataclasses.dataclass
class GetResult:
    request_id: Optional[str]
    resources: List[Dict[str, Any]]
    response_headers: Optional[List[str]]
