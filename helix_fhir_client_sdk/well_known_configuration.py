from datetime import datetime
from typing import NamedTuple, Optional


class WellKnownConfigurationCacheEntry(NamedTuple):
    """
    stores the tuple in the cache
    """

    auth_url: Optional[str]
    last_updated_utc: datetime
