from helix_fhir_client_sdk.graph.resource_type_completion_event import (
    ResourceTypeCompletionEvent,
)


def test_resource_type_completion_event_construction() -> None:
    event = ResourceTypeCompletionEvent(
        resource_types=["Condition"],
        resource_count=12,
        graph_depth=1,
        urls=["https://example.com/fhir/Condition?patient=123"],
        link_index=0,
        client_person_id="client-1",
        connection_name="Aetna Sandbox",
    )
    assert event.resource_types == ["Condition"]
    assert event.resource_count == 12
    assert event.graph_depth == 1
    assert event.urls == ["https://example.com/fhir/Condition?patient=123"]
    assert event.link_index == 0
    assert event.client_person_id == "client-1"
    assert event.connection_name == "Aetna Sandbox"


def test_resource_type_completion_event_multiple_types() -> None:
    # A single GraphDefinition link's `target` array can name more than one type
    # (e.g. a link with both AllergyIntolerance and CarePlan targets), so this
    # must accept more than one resource type — and more than one queried URL —
    # per event.
    event = ResourceTypeCompletionEvent(
        resource_types=["AllergyIntolerance", "CarePlan"],
        resource_count=5,
        graph_depth=0,
        urls=[
            "https://example.com/fhir/AllergyIntolerance?patient=123",
            "https://example.com/fhir/CarePlan?patient=123",
        ],
        link_index=0,
        client_person_id="client-1",
        connection_name="Aetna Sandbox",
    )
    assert len(event.resource_types) == 2
    assert len(event.urls) == 2
    assert event.client_person_id == "client-1"
    assert event.connection_name == "Aetna Sandbox"
