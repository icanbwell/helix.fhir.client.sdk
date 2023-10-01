import dataclasses
from typing import List, Dict, Any, Optional, Tuple


@dataclasses.dataclass
class PagingResult:
    request_id: Optional[str]
    resources: List[Dict[str, Any]]
    page_number: int
    response_headers: Optional[List[Tuple[str, Any]]]
