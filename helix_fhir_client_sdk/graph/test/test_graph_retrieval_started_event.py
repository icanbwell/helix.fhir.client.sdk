from helix_fhir_client_sdk.graph.graph_retrieval_started_event import (
    GraphRetrievalStartedEvent,
)


def test_graph_retrieval_started_event_construction() -> None:
    event = GraphRetrievalStartedEvent(
        start_resource_type="Patient",
        url="https://example.com/fhir",
    )
    assert event.start_resource_type == "Patient"
    assert event.url == "https://example.com/fhir"
