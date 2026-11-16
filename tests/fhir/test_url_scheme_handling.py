"""
DCON-6330: Regression tests for URL scheme handling on pagination links

A FHIR server builds the Bundle ``next`` link from the request it received
(``protocol://host/path``). Behind a proxy that terminates TLS it writes
``https://`` even when the client called it over ``http://``. A client that can
only reach the host over http (for example through a gateway that only serves http) then fails on page two with a connection error
to port 443.

Fix: when the next URL has the same host as the base URL and no explicit port,
the SDK uses the scheme of the base URL, the one the client was configured with.
Combined with INC-285 (port), ``align_next_url_with_base_url`` makes a same-host
next link use the scheme and port of the base URL.
"""

import pytest

from helix_fhir_client_sdk.utilities.url_checker import UrlChecker


class TestPreserveSchemeFromBaseUrl:
    """Tests for UrlChecker.preserve_scheme_from_base_url()"""

    @pytest.mark.parametrize(
        ("base_url", "next_url", "expected"),
        [
            pytest.param(
                "http://fhir.example.com/4_0_0",
                "https://fhir.example.com/4_0_0/Patient?_count=100&id:above=abc-123",
                "http://fhir.example.com/4_0_0/Patient?_count=100&id:above=abc-123",
                id="https-next-link-on-http-client",
            ),
            pytest.param(
                "https://fhir.example.org/4_0_0",
                "http://fhir.example.org/4_0_0/Patient?_count=10",
                "https://fhir.example.org/4_0_0/Patient?_count=10",
                id="http-next-link-on-https-client",
            ),
            pytest.param(
                "http://FHIR.Example.com/4_0_0",
                "https://fhir.example.com/4_0_0/Task?_count=10",
                "http://fhir.example.com/4_0_0/Task?_count=10",
                id="host-compared-case-insensitively",
            ),
            pytest.param(
                "http://fhir-server/4_0_0",
                "https://fhir-server/4_0_0/Observation?_count=10&_sort=date#section",
                "http://fhir-server/4_0_0/Observation?_count=10&_sort=date#section",
                id="keeps-query-and-fragment",
            ),
        ],
    )
    def test_uses_base_scheme_for_same_host(self, base_url: str, next_url: str, expected: str) -> None:
        result = UrlChecker.preserve_scheme_from_base_url(base_url=base_url, next_url=next_url)

        assert result == expected

    @pytest.mark.parametrize(
        ("base_url", "next_url"),
        [
            pytest.param(
                "http://fhir-server/4_0_0",
                "http://fhir-server/4_0_0/Observation?_count=10",
                id="same-scheme",
            ),
            pytest.param(
                "http://fhir-server-1/4_0_0",
                "https://fhir-server-2/4_0_0/Observation?_count=10",
                id="different-host",
            ),
            pytest.param(
                "http://fhir-server/4_0_0",
                "https://fhir-server:8443/4_0_0/Observation?_count=10",
                id="next-url-has-explicit-port",
            ),
        ],
    )
    def test_leaves_next_url_unchanged(self, base_url: str, next_url: str) -> None:
        result = UrlChecker.preserve_scheme_from_base_url(base_url=base_url, next_url=next_url)

        assert result == next_url

    def test_does_not_re_encode_the_query(self) -> None:
        # The id:above keyset cursor must reach the server exactly as it sent it.
        next_url = "https://fhir/4_0_0/Patient?identifier=a%7Cb&id:above=x&_elements=id,meta"

        result = UrlChecker.preserve_scheme_from_base_url(base_url="http://fhir/4_0_0", next_url=next_url)

        assert result == "http://fhir/4_0_0/Patient?identifier=a%7Cb&id:above=x&_elements=id,meta"


class TestAlignNextUrlWithBaseUrl:
    """Tests for UrlChecker.align_next_url_with_base_url(): scheme first, then port (INC-285)"""

    @pytest.mark.parametrize(
        ("base_url", "next_url", "expected"),
        [
            pytest.param(
                "http://fhir-server:3000/4_0_0/Observation",
                "https://fhir-server/4_0_0/Observation?_count=10",
                "http://fhir-server:3000/4_0_0/Observation?_count=10",
                id="scheme-and-port-from-base",
            ),
            pytest.param(
                "http://fhir-server-mcp:3000/4_0_0/Observation",
                "http://fhir-server-mcp/4_0_0/Observation?_count=10&_getpagesoffset=10",
                "http://fhir-server-mcp:3000/4_0_0/Observation?_count=10&_getpagesoffset=10",
                id="inc-285-port-only",
            ),
            pytest.param(
                "http://fhir.example.com/4_0_0",
                "https://fhir.example.com/4_0_0/Patient?id:above=abc",
                "http://fhir.example.com/4_0_0/Patient?id:above=abc",
                id="scheme-only",
            ),
            pytest.param(
                "https://fhir.example.net/4_0_0/Observation",
                "https://fhir.example.net/4_0_0/Observation?_count=10",
                "https://fhir.example.net/4_0_0/Observation?_count=10",
                id="already-aligned",
            ),
            pytest.param(
                "http://fhir-server-1:3000/4_0_0",
                "https://fhir-server-2/4_0_0/Observation?_count=10",
                "https://fhir-server-2/4_0_0/Observation?_count=10",
                id="other-host-untouched",
            ),
        ],
    )
    def test_aligns_same_host_next_url(self, base_url: str, next_url: str, expected: str) -> None:
        result = UrlChecker.align_next_url_with_base_url(base_url=base_url, next_url=next_url)

        assert result == expected
