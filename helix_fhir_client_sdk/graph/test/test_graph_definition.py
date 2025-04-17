import pytest
from helix_fhir_client_sdk.graph.graph_definition import (
    GraphDefinition,
    GraphDefinitionLink,
    GraphDefinitionTarget,
)


def test_graph_definition_initialization() -> None:
    link = GraphDefinitionLink(
        path="test_path",
        target=[
            GraphDefinitionTarget(type_="test_type", params="test_params", link=None)
        ],
    )
    graph_definition = GraphDefinition(
        id_="test_id", name="test_name", start="test_start", link=[link]
    )

    assert graph_definition.id_ == "test_id"
    assert graph_definition.name == "test_name"
    assert graph_definition.start == "test_start"
    assert graph_definition.link == [link]


def test_graph_definition_to_dict() -> None:
    link = GraphDefinitionLink(
        path="test_path",
        target=[
            GraphDefinitionTarget(type_="test_type", params="test_params", link=None)
        ],
    )
    graph_definition = GraphDefinition(
        id_="test_id", name="test_name", start="test_start", link=[link]
    )

    expected_dict = {
        "resourceType": "GraphDefinition",
        "id": "test_id",
        "name": "test_name",
        "status": "active",
        "start": "test_start",
        "link": [
            {
                "path": "test_path",
                "target": [
                    {"type": "test_type", "params": "test_params", "link": None}
                ],
            }
        ],
    }

    assert graph_definition.to_dict() == expected_dict


def test_graph_definition_from_dict() -> None:
    input_dict = {
        "id": "test_id",
        "name": "test_name",
        "start": "test_start",
        "link": [
            {
                "path": "test_path",
                "target": [
                    {"type": "test_type", "params": "test_params", "link": None}
                ],
            }
        ],
    }

    graph_definition = GraphDefinition.from_dict(input_dict)

    assert graph_definition.id_ == "test_id"
    assert graph_definition.name == "test_name"
    assert graph_definition.start == "test_start"
    assert len(graph_definition.link) == 1
    assert graph_definition.link[0].path == "test_path"
    assert len(graph_definition.link[0].target) == 1
    assert graph_definition.link[0].target[0].type_ == "test_type"
    assert graph_definition.link[0].target[0].params == "test_params"
    assert graph_definition.link[0].target[0].link is None
