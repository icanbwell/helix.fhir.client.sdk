import dataclasses
from datetime import datetime
from typing import Optional


@dataclasses.dataclass(slots=True)
class GetAccessTokenResult:
    """
    Result of a token refresh
    """

    access_token: Optional[str]
    """ New access token """

    expiry_date: Optional[datetime]
    """ Expiry date of the new token """
