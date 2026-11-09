from collections.abc import Mapping


class HeaderRedactor:
    """
    Redacts the values of the HTTP headers that carry credentials, so that request headers can go
    into exceptions, logs and telemetry.
    """

    REDACTED: str = "[REDACTED]"
    # a header whose name, in lowercase, contains one of these parts carries a credential, for example
    # Authorization, Cookie, X-Api-Key, X-Auth-Token, X-JWT-Assertion or X-IBM-Client-Id
    _CREDENTIAL_HEADER_NAME_PARTS: tuple[str, ...] = (
        "assertion",
        "auth",
        "client-id",
        "cookie",
        "credential",
        "jwt",
        "key",
        "password",
        "secret",
        "session",
        "signature",
        "token",
    )

    @classmethod
    def is_credential_header(cls, *, name: str) -> bool:
        """
        Returns True when the header carries a credential.

        :param name: the header name, in any case
        """
        lowercase_name = name.lower()
        return any(part in lowercase_name for part in cls._CREDENTIAL_HEADER_NAME_PARTS)

    @classmethod
    def redact(cls, *, headers: Mapping[str, str] | None) -> dict[str, str]:
        """
        Returns a copy of the headers in which the value of each credential header is redacted.

        :param headers: the request headers
        :return: the redacted copy
        """
        return {
            name: cls.REDACTED if cls.is_credential_header(name=name) else value
            for name, value in (headers or {}).items()
        }
