import dataclasses
from datetime import datetime


@dataclasses.dataclass(slots=True)
class GetAccessTokenResult:
    """
    Result of a token refresh
    """

    access_token: str | None
    """ New access token """

    expiry_date: datetime | None
    """ Expiry date of the new token """
