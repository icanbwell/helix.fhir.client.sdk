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
        outcome="success",
        error_type=None,
        error_message=None,
    )
    assert event.resource_types == ["Condition"]
    assert event.resource_count == 12
    assert event.graph_depth == 1
    assert event.urls == ["https://example.com/fhir/Condition?patient=123"]
    assert event.link_index == 0
    assert event.client_person_id == "client-1"
    assert event.connection_name == "Aetna Sandbox"
    assert event.outcome == "success"
    assert event.error_type is None
    assert event.error_message is None


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
        outcome="success",
        error_type=None,
        error_message=None,
    )
    assert len(event.resource_types) == 2
    assert len(event.urls) == 2
    assert event.client_person_id == "client-1"
    assert event.connection_name == "Aetna Sandbox"


def test_resource_type_completion_event_error_outcome() -> None:
    event = ResourceTypeCompletionEvent(
        resource_types=["AllergyIntolerance"],
        resource_count=0,
        graph_depth=0,
        urls=[],
        link_index=0,
        client_person_id="client-1",
        connection_name="Aetna Sandbox",
        outcome="error",
        error_type="RuntimeError",
        error_message="simulated network failure",
    )
    assert event.outcome == "error"
    assert event.error_type == "RuntimeError"
    assert event.error_message == "simulated network failure"


def test_resource_type_completion_event_not_found_outcome() -> None:
    event = ResourceTypeCompletionEvent(
        resource_types=["Condition"],
        resource_count=0,
        graph_depth=0,
        urls=["https://example.com/fhir/Condition?patient=123"],
        link_index=0,
        client_person_id="",
        connection_name="",
        outcome="not_found",
        error_type=None,
        error_message=None,
    )
    assert event.outcome == "not_found"


def test_resource_type_completion_event_scope_denied_outcome() -> None:
    event = ResourceTypeCompletionEvent(
        resource_types=["Condition"],
        resource_count=0,
        graph_depth=0,
        urls=[],
        link_index=0,
        client_person_id="",
        connection_name="",
        outcome="scope_denied",
        error_type=None,
        error_message=None,
    )
    assert event.outcome == "scope_denied"
