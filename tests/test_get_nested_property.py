from typing import Any

import pytest

from helix_fhir_client_sdk.dictionary_parser import DictionaryParser


@pytest.mark.parametrize(
    argnames="parent,path,expected_result",
    argvalues=[
        ({"status": "active"}, "status", "active"),
        (
            {"status": [{"reference": "123"}, {"reference": "456"}]},
            "status[x].reference",
            ["123", "456"],
        ),
        (
            {"foo": {"status": [{"reference": "123"}, {"reference": "456"}]}},
            "foo.status[x].reference",
            ["123", "456"],
        ),
        (
            {
                "foo": {
                    "status": [
                        {"bar": [{"reference": "123"}]},
                        {"bar": [{"reference": "456"}, {"reference": "789"}]},
                    ]
                }
            },
            "foo.status[x].bar[x].reference",
            ["123", "456", "789"],
        ),
        (
            {
                "foo": {
                    "status": [
                        {"bar": {"reference": "123"}},
                        {"bar": {"reference": "456"}},
                    ]
                }
            },
            "foo.status[x].bar.reference",
            ["123", "456"],
        ),
        (
            {
                "content": [
                    {"attachment": {"url": "Binary/123"}},
                    {"attachment": {"url": "Binary/456"}},
                ]
            },
            "content[x].attachment.url",
            ["Binary/123", "Binary/456"],
        ),
        (
            {
                "insurance": [
                    {"coverage": {"reference": "Coverage/123"}},
                    {"coverage": {"reference": "Coverage/456"}},
                ]
            },
            "insurance[x].coverage.reference",
            ["Coverage/123", "Coverage/456"],
        ),
    ],
    ids=[
        "simple",
        "list at end of field",
        "list in a list",
        "list in middle of field",
        "nested list two level",
        "nested property is a url",
        "real example",
    ],
)
def test_get_nested_property(
    parent: dict[str, Any],
    path: str,
    expected_result: list[dict[str, Any]] | dict[str, Any] | str | None,
) -> None:
    result = DictionaryParser.get_nested_property(parent=parent, path=path)
    assert result == expected_result
