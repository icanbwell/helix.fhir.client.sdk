class FhirClientSdkOpenTelemetryAttributeNames:
    """Constants for OpenTelemetry attribute names used in the FHIR Client SDK."""

    URL: str = "fhir.client_sdk.url"
    RESOURCE: str = "fhir.client_sdk.resource"
    JSON_DATA_COUNT: str = "fhir.client_sdk.json_data.count"
    BATCH_SIZE: str = "fhir.client_sdk.batch.size"
    # the attributes of the graph link group span: numbers only, no URLs and no ids
    # the depth of the links of the group: 0 for the links of the start resource
    GRAPH_DEPTH: str = "fhir.client_sdk.graph.depth"
    # the position of the group in the groups of its depth, which run one after the other: 0 for the first
    GRAPH_LINK_GROUP_INDEX: str = "fhir.client_sdk.graph.link_group.index"
    # the number of links in the group
    GRAPH_LINK_COUNT: str = "fhir.client_sdk.graph.link.count"
    # the number of requests that the client started while the group ran: one for each page, retries not counted.
    # Exact only when the client runs one traversal at a time and its caller sends no requests on the same client
    # during the group
    GRAPH_CHILD_GET_COUNT: str = "fhir.client_sdk.graph.child_get.count"
