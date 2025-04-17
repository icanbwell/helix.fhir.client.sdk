from datetime import datetime
from typing import NamedTuple


class WellKnownConfigurationCacheEntry(NamedTuple):
    """
    stores the tuple in the cache
    """

    auth_url: str | None
    last_updated_utc: datetime
