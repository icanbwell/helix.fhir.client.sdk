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


def test_graph_definition_target_to_dict() -> None:
    target = GraphDefinitionTarget(type_="test_type", params="test_params", link=None)
    expected_dict = {"type": "test_type", "params": "test_params"}
    assert target.to_dict() == expected_dict


def test_graph_definition_target_from_dict() -> None:
    input_dict = {"type": "test_type", "params": "test_params"}
    target = GraphDefinitionTarget.from_dict(input_dict)
    assert target.type_ == "test_type"
    assert target.params == "test_params"
    assert target.link is None


def test_graph_definition_link_to_dict() -> None:
    target = GraphDefinitionTarget(type_="test_type", params="test_params", link=None)
    link = GraphDefinitionLink(path="test_path", target=[target])
    expected_dict = {
        "path": "test_path",
        "target": [{"type": "test_type", "params": "test_params"}],
    }
    assert link.to_dict() == expected_dict


def test_graph_definition_link_from_dict() -> None:
    input_dict = {
        "path": "test_path",
        "target": [{"type": "test_type", "params": "test_params"}],
    }
    link = GraphDefinitionLink.from_dict(input_dict)
    assert link.path == "test_path"
    assert len(link.target) == 1
    assert link.target[0].type_ == "test_type"
    assert link.target[0].params == "test_params"
    assert link.target[0].link is None


def test_graph_definition_target_to_dict_with_link() -> None:
    nested_link = GraphDefinitionLink(
        path="nested_path",
        target=[
            GraphDefinitionTarget(type_="nested_type", params="nested_params", link=None)
        ],
    )
    target = GraphDefinitionTarget(type_="test_type", params="test_params", link=[nested_link])
    expected_dict = {
        "type": "test_type",
        "params": "test_params",
        "link": [
            {
                "path": "nested_path",
                "target": [
                    {"type": "nested_type", "params": "nested_params"}
                ],
            }
        ],
    }
    assert target.to_dict() == expected_dict


def test_graph_definition_target_from_dict_with_link() -> None:
    input_dict = {
        "type": "test_type",
        "params": "test_params",
        "link": [
            {
                "path": "nested_path",
                "target": [
                    {"type": "nested_type", "params": "nested_params"}
                ],
            }
        ],
    }
    target = GraphDefinitionTarget.from_dict(input_dict)
    assert target.type_ == "test_type"
    assert target.params == "test_params"
    assert len(target.link) == 1
    assert target.link[0].path == "nested_path"
    assert len(target.link[0].target) == 1
    assert target.link[0].target[0].type_ == "nested_type"
    assert target.link[0].target[0].params == "nested_params"
    assert target.link[0].target[0].link is None


def test_graph_definition_link_to_dict_with_nested_target() -> None:
    nested_target = GraphDefinitionTarget(type_="nested_type", params="nested_params", link=None)
    link = GraphDefinitionLink(path="test_path", target=[nested_target])
    expected_dict = {
        "path": "test_path",
        "target": [
            {"type": "nested_type", "params": "nested_params"}
        ],
    }
    assert link.to_dict() == expected_dict


def test_graph_definition_link_from_dict_with_nested_target() -> None:
    input_dict = {
        "path": "test_path",
        "target": [
            {"type": "nested_type", "params": "nested_params"}
        ],
    }
    link = GraphDefinitionLink.from_dict(input_dict)
    assert link.path == "test_path"
    assert len(link.target) == 1
    assert link.target[0].type_ == "nested_type"
    assert link.target[0].params == "nested_params"
    assert link.target[0].link is None
