from helix_fhir_client_sdk.graph.resource_type_started_event import (
    ResourceTypeStartedEvent,
)


def test_resource_type_started_event_construction() -> None:
    event = ResourceTypeStartedEvent(
        resource_types=["Condition"],
        graph_depth=1,
        url="https://example.com/fhir",
        link_index=-1,
    )
    assert event.resource_types == ["Condition"]
    assert event.graph_depth == 1
    assert event.url == "https://example.com/fhir"
    assert event.link_index == -1
