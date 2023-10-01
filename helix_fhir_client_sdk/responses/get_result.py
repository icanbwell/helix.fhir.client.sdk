import dataclasses
from typing import List, Dict, Any, Optional, Tuple


@dataclasses.dataclass
class GetResult:
    request_id: Optional[str]
    resources: List[Dict[str, Any]]
    response_headers: Optional[List[Tuple[str, Any]]]
