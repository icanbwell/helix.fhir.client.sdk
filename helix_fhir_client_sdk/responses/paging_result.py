import dataclasses
from typing import List, Dict, Any


@dataclasses.dataclass
class PagingResult:
    resources: List[Dict[str, Any]]
    page_number: int
