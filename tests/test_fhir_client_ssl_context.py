"""
Tests for the TLS trust store behind FhirClient.create_http_session().

The SDK must trust the union of the operating system's CA store and certifi's bundle.
A CA installed in the runtime image (for example with ``update-ca-certificates``) then
works without anyone patching certifi's bundle.
"""

import ssl
from pathlib import Path
from typing import cast

import aiohttp
import certifi
import pytest

from helix_fhir_client_sdk.fhir_client import FhirClient

# Self-signed, test-only CA. Its private key was discarded at generation time, so it can
# sign nothing. Its subject is unique: finding it in a context proves the OS store was
# consulted, because it is never part of certifi.
TEST_ONLY_CA_PEM = Path(__file__).parent / "certs" / "helix_fhir_client_sdk_test_ca.pem"
TEST_ONLY_CA_COMMON_NAME = "helix-fhir-client-sdk test CA"


def _common_names(ssl_context: ssl.SSLContext) -> set[str]:
    """Common names of every CA certificate the context accepts as an issuer."""
    names: set[str] = set()
    for ca in ssl_context.get_ca_certs():
        # typeshed types every field of the cert dict as a union, so narrow "subject" to
        # its documented shape: a tuple of RDNs, each a tuple of (attribute, value) pairs.
        subject = cast(tuple[tuple[tuple[str, str], ...], ...], ca["subject"])
        for rdn in subject:
            for key, value in rdn:
                if key == "commonName":
                    names.add(value)
    return names


def _count_pem_certificates(path: str) -> int:
    return Path(path).read_text().count("-----BEGIN CERTIFICATE-----")


def test_create_ssl_context_trusts_certificates_from_the_os_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A CA that exists only in the OS trust store is accepted as an issuer."""
    # Arrange: SSL_CERT_FILE is how OpenSSL lets a process point the OS store at a file.
    monkeypatch.setenv("SSL_CERT_FILE", str(TEST_ONLY_CA_PEM))

    # Act
    ssl_context = FhirClient.create_ssl_context()

    # Assert
    assert TEST_ONLY_CA_COMMON_NAME in _common_names(ssl_context)


def test_create_ssl_context_still_trusts_the_certifi_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Consulting the OS store is additive: every certifi root stays trusted."""
    # Arrange
    monkeypatch.setenv("SSL_CERT_FILE", str(TEST_ONLY_CA_PEM))

    # Act
    ssl_context = FhirClient.create_ssl_context()

    # Assert
    assert len(ssl_context.get_ca_certs()) >= _count_pem_certificates(certifi.where())


def test_create_ssl_context_keeps_strict_verification() -> None:
    """Widening the trust store must not weaken hostname or chain verification."""
    # Act
    ssl_context = FhirClient.create_ssl_context()

    # Assert
    assert ssl_context.verify_mode == ssl.CERT_REQUIRED
    assert ssl_context.check_hostname is True


async def test_create_http_session_uses_the_sdk_ssl_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The session built for FHIR calls carries the SDK's trust policy, not aiohttp's default."""
    # Arrange
    sentinel_context = ssl.create_default_context()
    monkeypatch.setattr(FhirClient, "create_ssl_context", staticmethod(lambda: sentinel_context))
    fhir_client = FhirClient().url("http://example.com")

    # Act
    session = fhir_client.create_http_session()

    # Assert
    try:
        connector = session.connector
        assert isinstance(connector, aiohttp.TCPConnector)
        # aiohttp has no public getter for the connector's ssl setting.
        assert connector._ssl is sentinel_context
    finally:
        await session.close()
