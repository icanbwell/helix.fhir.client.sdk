import re
from urllib.parse import urlsplit


class UrlRedactor:
    """
    Gives the forms of a URL that are safe to put in logs and telemetry.

    The user info, the query, the fragment and the resource ids in the path of a URL can contain
    patient identifiers, page cursors and tokens, so these forms leave them out.
    """

    ID_PLACEHOLDER: str = "{id}"
    VERSION_ID_PLACEHOLDER: str = "{vid}"
    VALUE_PLACEHOLDER: str = "{value}"
    # a FHIR resource type is one or more capitalized words, for example Patient or AllergyIntolerance
    _RESOURCE_TYPE_PATTERN: re.Pattern[str] = re.compile(r"(?:[A-Z][a-z]+)+")
    # a FHIR id has at most 64 characters, so a longer path segment is an opaque value such as a page token
    _MAX_FHIR_ID_LENGTH: int = 64

    @staticmethod
    def get_host(*, url: str) -> str | None:
        """
        Returns the host name of the URL, without user info and port.

        :param url: the URL
        :return: the host name in lowercase, or None when the URL has no host
        """
        return urlsplit(url).hostname

    @staticmethod
    def get_url_template(*, url: str) -> str:
        """
        Returns the scheme, host, port and path of the URL. In the path, the segment after a resource
        type becomes {id}, the segment after _history becomes {vid}, and a segment that is longer than
        a FHIR id becomes {value}. The user info, the query and the fragment are left out.

        Example: https://fhir.example.com/4_0_0/Patient/123/$everything?_since=2024-01-01
        gives https://fhir.example.com/4_0_0/Patient/{id}/$everything

        :param url: the URL
        :return: the URL template
        """
        parts = urlsplit(url)
        template_segments: list[str] = []
        previous_segment_is_resource_type = False
        previous_segment_is_history = False
        for segment in parts.path.split("/"):
            if previous_segment_is_resource_type and segment and not segment.startswith(("$", "_")):
                template_segment = UrlRedactor.ID_PLACEHOLDER
            elif previous_segment_is_history and segment:
                template_segment = UrlRedactor.VERSION_ID_PLACEHOLDER
            elif len(segment) > UrlRedactor._MAX_FHIR_ID_LENGTH:
                template_segment = UrlRedactor.VALUE_PLACEHOLDER
            else:
                template_segment = segment
            template_segments.append(template_segment)
            previous_segment_is_resource_type = (
                template_segment == segment and UrlRedactor._RESOURCE_TYPE_PATTERN.fullmatch(segment) is not None
            )
            previous_segment_is_history = segment == "_history"
        path_template = "/".join(template_segments)

        # the network location without the user info: the host and the port, as the URL gives them
        host_and_port = parts.netloc.rpartition("@")[2]
        if not host_and_port:
            return path_template
        return f"{parts.scheme}://{host_and_port}{path_template}"
