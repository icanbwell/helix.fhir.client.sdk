class FhirClientSdkOpenTelemetrySpanNames:
    """Span names for OpenTelemetry tracing in the FHIR Client SDK."""

    GET: str = "fhir.client_sdk.get"
    GET_STREAMING: str = "fhir.client_sdk.streaming.get"
    GET_ACCESS_TOKEN: str = "fhir.client_sdk.access_token.get"
    HTTP_GET: str = "fhir.client_sdk.http.get"
    HANDLE_RESPONSE: str = "fhir.client_sdk.handle_response"
    DELETE: str = "fhir.client_sdk.delete"
    UPDATE: str = "fhir.client_sdk.update"
    PATCH: str = "fhir.client_sdk.patch"
    MERGE: str = "fhir.client_sdk.merge"
