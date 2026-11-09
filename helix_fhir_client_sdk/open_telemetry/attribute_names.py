class FhirClientSdkOpenTelemetryAttributeNames:
    """Constants for OpenTelemetry attribute names used in the FHIR Client SDK."""

    URL: str = "fhir.client_sdk.url"
    RESOURCE: str = "fhir.client_sdk.resource"
    JSON_DATA_COUNT: str = "fhir.client_sdk.json_data.count"
    BATCH_SIZE: str = "fhir.client_sdk.batch.size"
