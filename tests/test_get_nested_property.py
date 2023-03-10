from helix_fhir_client_sdk.dictionary_parser import DictionaryParser


def test_get_nested_property_simple() -> None:
    parent = {"status": "active"}
    result = DictionaryParser.get_nested_property(parent=parent, path="status")
    assert result == "active"


def test_get_nested_property_list() -> None:
    parent = {"status": [{"reference": "123"}, {"reference": "456"}]}
    result = DictionaryParser.get_nested_property(
        parent=parent, path="status[x].reference"
    )
    assert result == ["123", "456"]  # type: ignore


def test_get_nested_property_nested_list() -> None:
    parent = {"foo": {"status": [{"reference": "123"}, {"reference": "456"}]}}
    result = DictionaryParser.get_nested_property(
        parent=parent, path="foo.status[x].reference"
    )
    assert result == ["123", "456"]  # type: ignore


def test_get_nested_property_nested_list_two_level() -> None:
    parent = {
        "foo": {
            "status": [{"bar": [{"reference": "123"}]}, {"bar": [{"reference": "456"}]}]
        }
    }
    result = DictionaryParser.get_nested_property(
        parent=parent, path="foo.status[x].bar[x].reference"
    )
    assert result == ["123", "456"]  # type: ignore
