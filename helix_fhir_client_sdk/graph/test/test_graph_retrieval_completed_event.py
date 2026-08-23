from helix_fhir_client_sdk.graph.graph_retrieval_completed_event import (
    GraphRetrievalCompletedEvent,
)


def test_graph_retrieval_completed_event_construction() -> None:
    event = GraphRetrievalCompletedEvent(
        resource_types=["Patient", "AllergyIntolerance", "CarePlan"],
        total_resource_count=3,
        max_graph_depth=0,
        urls=[
            "https://example.com/fhir/Patient/123",
            "https://example.com/fhir/AllergyIntolerance?patient=123",
            "https://example.com/fhir/CarePlan?patient=123",
        ],
        client_person_id="client-1",
        connection_name="Aetna Sandbox",
    )
    assert event.resource_types == ["Patient", "AllergyIntolerance", "CarePlan"]
    assert event.total_resource_count == 3
    assert event.max_graph_depth == 0
    assert len(event.urls) == 3
    assert event.client_person_id == "client-1"
    assert event.connection_name == "Aetna Sandbox"


def test_graph_retrieval_completed_event_zero_results() -> None:
    # Fires even when the start resource itself returned zero results —
    # callers need a definitive "done" signal either way.
    event = GraphRetrievalCompletedEvent(
        resource_types=[],
        total_resource_count=0,
        max_graph_depth=0,
        urls=["https://example.com/fhir/Patient/123"],
        client_person_id="client-1",
        connection_name="Aetna Sandbox",
    )
    assert event.resource_types == []
    assert event.total_resource_count == 0
    assert event.client_person_id == "client-1"
    assert event.connection_name == "Aetna Sandbox"
