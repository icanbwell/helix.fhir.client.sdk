from typing import cast
from urllib.parse import urlparse

from furl import furl


class UrlChecker:
    @staticmethod
    def is_absolute_url(*, url: str | furl) -> bool:
        """
        Determine if a URL is absolute or relative.

        Args:
            url (Union[str, furl]): The URL to check

        Returns:
            bool: True if the URL is absolute, False if relative
        """
        # If input is a furl object, convert to string
        if isinstance(url, furl):
            url = str(url)

        # Use urlparse to check for scheme and netloc
        parsed_url = urlparse(url)

        # An absolute URL must have a scheme (http, https, etc.)
        return bool(parsed_url.scheme)

    @staticmethod
    def convert_relative_url_to_absolute_url(*, base_url: str, relative_url: str | furl) -> str:
        """
        Convert a relative URL to an absolute URL using the provided base URL.

        Args:
            base_url (str): The base URL to resolve against
            relative_url (Union[str, furl]): The relative URL to convert

        Returns:
            furl: An absolute URL

        Raises:
            ValueError: If the base URL is not absolute
        """
        # Ensure base URL is absolute
        base = furl(base_url)
        if not base.scheme or not base.host:
            raise ValueError(f"Base URL must be absolute. Provided: {base_url}")

        # Convert relative_url to furl if it's a string
        if isinstance(relative_url, str):
            relative = furl(relative_url)
        else:
            relative = relative_url

        # Combine base and relative URLs
        absolute_url = base.copy()

        absolute_url = absolute_url.join(relative)

        # # Update path
        # if relative.path:
        #     absolute_url.path.segments += relative.path.segments
        #
        # # Update query parameters
        # if relative.query:
        #     absolute_url.query.set(relative.query.params)
        #
        # # Update fragment if present
        # if relative.fragment:
        #     absolute_url.fragment = relative.fragment
        #
        return cast(str, absolute_url.url)
