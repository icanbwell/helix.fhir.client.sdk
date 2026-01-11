from typing import cast
from urllib.parse import urlparse

from furl import furl


class UrlChecker:
    @staticmethod
    def preserve_port_from_base_url(*, base_url: str, next_url: str) -> str:
        """
        INC-285: Preserve the port from the base URL when the next URL has the same host
        but is missing the port.

        This fixes an issue where FHIR servers generate pagination URLs without the port,
        causing requests to go to the default port (80 for HTTP, 443 for HTTPS) instead
        of the correct port.

        Example:
            base_url: http://fhir-server:3000/4_0_0/Observation
            next_url: http://fhir-server/4_0_0/Observation?_count=10&_getpagesoffset=10
            result:   http://fhir-server:3000/4_0_0/Observation?_count=10&_getpagesoffset=10

        Args:
            base_url (str): The original base URL with the correct port
            next_url (str): The URL returned by the FHIR server (may be missing port)

        Returns:
            str: The next URL with the port preserved from the base URL if applicable
        """
        base_parsed = urlparse(base_url)
        next_parsed = urlparse(next_url)

        # Only apply fix if:
        # 1. Both URLs have the same scheme
        # 2. Both URLs have the same hostname (ignoring port)
        # 3. Base URL has an explicit port
        # 4. The next URL does NOT have an explicit port
        base_hostname = base_parsed.hostname
        next_hostname = next_parsed.hostname

        if (
            base_parsed.scheme == next_parsed.scheme
            and base_hostname == next_hostname
            and base_parsed.port is not None
            and next_parsed.port is None
        ):
            # Reconstruct the next URL with the port from base URL
            next_furl = furl(next_url)
            next_furl.port = base_parsed.port
            return str(next_furl)

        return next_url

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

        return cast(str, absolute_url.url)
