"""
INC-285: Regression tests for URL port handling

This module tests the fix for a bug where FHIR servers generate pagination URLs
without the port number, causing connection failures when the SDK follows the
"next" link in Bundle responses.

Root cause: FHIR server returns absolute URLs like http://fhir-server/path
instead of http://fhir-server:3000/path, causing requests to go to port 80.

Fix: The SDK now preserves the port from the base URL when the next URL has
the same host but is missing the port.
"""

from helix_fhir_client_sdk.utilities.url_checker import UrlChecker


class TestPreservePortFromBaseUrl:
    """Tests for UrlChecker.preserve_port_from_base_url()"""

    def test_preserves_port_when_next_url_missing_port(self) -> None:
        """
        INC-285: When next_url has the same host but missing port, preserve port from base_url
        """
        base_url = "http://fhir-server-mcp:3000/4_0_0/Observation"
        next_url = "http://fhir-server-mcp/4_0_0/Observation?_count=10&_getpagesoffset=10"

        result = UrlChecker.preserve_port_from_base_url(base_url=base_url, next_url=next_url)

        assert result == "http://fhir-server-mcp:3000/4_0_0/Observation?_count=10&_getpagesoffset=10"

    def test_does_not_modify_when_ports_match(self) -> None:
        """
        When both URLs have the same port, return next_url unchanged
        """
        base_url = "http://fhir-server:3000/4_0_0/Observation"
        next_url = "http://fhir-server:3000/4_0_0/Observation?_count=10"

        result = UrlChecker.preserve_port_from_base_url(base_url=base_url, next_url=next_url)

        assert result == next_url

    def test_does_not_modify_when_base_url_has_no_port(self) -> None:
        """
        When base_url has no explicit port, return next_url unchanged
        """
        base_url = "http://fhir-server/4_0_0/Observation"
        next_url = "http://fhir-server/4_0_0/Observation?_count=10"

        result = UrlChecker.preserve_port_from_base_url(base_url=base_url, next_url=next_url)

        assert result == next_url

    def test_does_not_modify_when_hosts_differ(self) -> None:
        """
        When hosts are different, return next_url unchanged (don't apply base port to different host)
        """
        base_url = "http://fhir-server-1:3000/4_0_0/Observation"
        next_url = "http://fhir-server-2/4_0_0/Observation?_count=10"

        result = UrlChecker.preserve_port_from_base_url(base_url=base_url, next_url=next_url)

        assert result == next_url

    def test_does_not_modify_when_schemes_differ(self) -> None:
        """
        When schemes are different (http vs https), return next_url unchanged
        """
        base_url = "https://fhir-server:3000/4_0_0/Observation"
        next_url = "http://fhir-server/4_0_0/Observation?_count=10"

        result = UrlChecker.preserve_port_from_base_url(base_url=base_url, next_url=next_url)

        assert result == next_url

    def test_handles_https_urls(self) -> None:
        """
        Should work correctly with HTTPS URLs
        """
        base_url = "https://fhir-server:8443/4_0_0/Observation"
        next_url = "https://fhir-server/4_0_0/Observation?_count=10"

        result = UrlChecker.preserve_port_from_base_url(base_url=base_url, next_url=next_url)

        assert result == "https://fhir-server:8443/4_0_0/Observation?_count=10"

    def test_preserves_query_params_and_fragments(self) -> None:
        """
        Should preserve all query parameters and fragments from next_url
        """
        base_url = "http://fhir-server:3000/4_0_0/Observation"
        next_url = "http://fhir-server/4_0_0/Observation?_count=10&_sort=date&patient=123#section"

        result = UrlChecker.preserve_port_from_base_url(base_url=base_url, next_url=next_url)

        assert result == "http://fhir-server:3000/4_0_0/Observation?_count=10&_sort=date&patient=123#section"

    def test_handles_different_paths(self) -> None:
        """
        Should work when base_url and next_url have different paths
        """
        base_url = "http://fhir-server:3000/4_0_0/Patient"
        next_url = "http://fhir-server/4_0_0/Observation?_count=10"

        result = UrlChecker.preserve_port_from_base_url(base_url=base_url, next_url=next_url)

        assert result == "http://fhir-server:3000/4_0_0/Observation?_count=10"

    def test_external_https_default_port_unchanged(self) -> None:
        """
        External HTTPS URLs with default port 443 should work correctly.
        This is the workaround scenario described in INC-285.
        """
        # When using external URLs like https://fhir-mcp.prod.bwell.zone/4_0_0/
        # Both base and next use default port 443, so no modification needed
        base_url = "https://fhir-mcp.prod.bwell.zone/4_0_0/Observation"
        next_url = "https://fhir-mcp.prod.bwell.zone/4_0_0/Observation?_count=10"

        result = UrlChecker.preserve_port_from_base_url(base_url=base_url, next_url=next_url)

        # Should remain unchanged since both use the default HTTPS port
        assert result == next_url

    def test_next_url_has_explicit_port(self) -> None:
        """
        When next_url already has an explicit port, don't override it
        """
        base_url = "http://fhir-server:3000/4_0_0/Observation"
        next_url = "http://fhir-server:8080/4_0_0/Observation?_count=10"

        result = UrlChecker.preserve_port_from_base_url(base_url=base_url, next_url=next_url)

        # Should not override the explicit port in next_url
        assert result == next_url


class TestUrlCheckerIsAbsoluteUrl:
    """Tests for UrlChecker.is_absolute_url()"""

    def test_absolute_http_url(self) -> None:
        assert UrlChecker.is_absolute_url(url="http://example.com/path") is True

    def test_absolute_https_url(self) -> None:
        assert UrlChecker.is_absolute_url(url="https://example.com/path") is True

    def test_relative_url_with_slash(self) -> None:
        assert UrlChecker.is_absolute_url(url="/4_0_0/Observation") is False

    def test_relative_url_without_slash(self) -> None:
        assert UrlChecker.is_absolute_url(url="4_0_0/Observation") is False


class TestConvertRelativeUrlToAbsoluteUrl:
    """Tests for UrlChecker.convert_relative_url_to_absolute_url()"""

    def test_converts_relative_to_absolute(self) -> None:
        result = UrlChecker.convert_relative_url_to_absolute_url(
            base_url="http://fhir-server:3000/4_0_0/", relative_url="/4_0_0/Observation?_count=10"
        )
        assert "fhir-server" in result
        assert "3000" in result
