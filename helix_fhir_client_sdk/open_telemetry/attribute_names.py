class FhirClientSdkOpenTelemetryAttributeNames:
    """Constants for OpenTelemetry attribute names used in the FHIR Client SDK."""

    URL: str = "fhir.client_sdk.url"
    RESOURCE: str = "fhir.client_sdk.resource"
    JSON_DATA_COUNT: str = "fhir.client_sdk.json_data.count"
    BATCH_SIZE: str = "fhir.client_sdk.batch.size"
    # the number of the attempt of an HTTP request: 1 for the first request, 2 for the first retry
    ATTEMPT: str = "fhir.client_sdk.attempt"
    # names from the OpenTelemetry semantic conventions
    SERVER_ADDRESS: str = "server.address"
    HTTP_RESPONSE_STATUS_CODE: str = "http.response.status_code"
