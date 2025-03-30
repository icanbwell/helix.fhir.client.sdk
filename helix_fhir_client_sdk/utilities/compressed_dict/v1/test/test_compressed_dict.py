import pytest
from typing import Any, cast

from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict import (
    CompressedDict,
    CompressedDictStorageMode,
)


class TestCompressedDict:
    def test_init_empty(self) -> None:
        """Test initialization with no initial data"""
        cd: CompressedDict[str, Any] = CompressedDict()
        assert len(cd) == 0
        assert cd._storage_mode == "raw"

    def test_init_with_dict(self) -> None:
        """Test initialization with initial dictionary"""
        initial_data = {"a": 1, "b": 2, "c": 3}
        cd = CompressedDict(initial_data)
        assert len(cd) == 3
        assert cd["a"] == 1
        assert cd["b"] == 2
        assert cd["c"] == 3

    @pytest.mark.parametrize("storage_mode", ["raw", "msgpack", "compressed_msgpack"])
    def test_storage_modes(self, storage_mode: CompressedDictStorageMode) -> None:
        """Test different storage modes"""
        initial_data = {"key": "value"}
        cd = CompressedDict(initial_data, storage_mode=storage_mode)
        assert cd._storage_mode == storage_mode
        assert cd["key"] == "value"

    def test_setitem_and_getitem(self) -> None:
        """Test setting and getting items"""
        cd: CompressedDict[str, Any] = CompressedDict()
        cd["key1"] = "value1"
        cd["key2"] = 42
        cd["key3"] = {"nested": "dict"}

        assert cd["key1"] == "value1"
        assert cd["key2"] == 42
        assert cd["key3"] == {"nested": "dict"}

    def test_delitem(self) -> None:
        """Test deleting items"""
        cd = CompressedDict({"a": 1, "b": 2})
        del cd["a"]

        assert len(cd) == 1
        assert "a" not in cd
        assert "b" in cd

    def test_contains(self) -> None:
        """Test key existence checks"""
        cd = CompressedDict({"a": 1, "b": 2})

        assert "a" in cd
        assert "b" in cd
        assert "c" not in cd

    def test_keys_and_values(self) -> None:
        """Test keys and values methods"""
        initial_data = {"a": 1, "b": 2, "c": 3}
        cd: CompressedDict[str, int] = CompressedDict(initial_data)

        assert set(cd.keys()) == {"a", "b", "c"}
        assert set(cd.values()) == {1, 2, 3}

    def test_items(self) -> None:
        """Test items method"""
        initial_data = {"a": 1, "b": 2, "c": 3}
        cd = CompressedDict(initial_data)

        assert set(cd.items()) == {("a", 1), ("b", 2), ("c", 3)}

    def test_get_method(self) -> None:
        """Test get method with default"""
        cd: CompressedDict[str, Any] = CompressedDict({"a": 1})

        assert cd.get("a") == 1
        assert cd.get("b") is None
        assert cd.get("b", "default") == "default"

    def test_to_dict(self) -> None:
        """Test conversion to standard dictionary"""
        initial_data = {"a": 1, "b": 2}
        cd = CompressedDict(initial_data)

        assert cd.to_dict() == initial_data

    def test_from_dict(self) -> None:
        """Test class method from_dict"""
        initial_data = {"a": 1, "b": 2}
        cd = CompressedDict.from_dict(initial_data)

        assert cd.to_dict() == initial_data

    def test_complex_nested_structures(self) -> None:
        """Test storage of complex nested structures"""
        complex_data = {
            "nested_dict": {"inner_key": "inner_value"},
            "list": [1, 2, 3],
            "mixed": [{"a": 1}, 2, "three"],
        }

        # Test each storage mode
        for mode in ["raw", "msgpack", "compressed_msgpack"]:
            cd = CompressedDict(
                complex_data, storage_mode=cast(CompressedDictStorageMode, mode)
            )

            assert cd["nested_dict"] == {"inner_key": "inner_value"}
            assert cd["list"] == [1, 2, 3]
            assert cd["mixed"] == [{"a": 1}, 2, "three"]

    def test_repr(self) -> None:
        """Test string representation"""
        cd = CompressedDict({"a": 1, "b": 2})
        repr_str = repr(cd)

        assert "storage_mode" in repr_str
        assert "items" in repr_str
        assert "'a': 1" in repr_str
        assert "'b': 2" in repr_str

    def test_error_handling(self) -> None:
        """Test error scenarios"""
        cd: CompressedDict[str, Any] = CompressedDict()

        # Test KeyError
        with pytest.raises(KeyError):
            _ = cd["non_existent_key"]

    @pytest.mark.parametrize("storage_mode", ["raw", "msgpack", "compressed_msgpack"])
    def test_large_data_handling(self, storage_mode: CompressedDictStorageMode) -> None:
        """Test handling of large datasets"""
        large_data = {f"key_{i}": f"value_{i}" for i in range(1000)}

        cd = CompressedDict(large_data, storage_mode=storage_mode)

        assert len(cd) == 1000
        assert cd["key_500"] == "value_500"
