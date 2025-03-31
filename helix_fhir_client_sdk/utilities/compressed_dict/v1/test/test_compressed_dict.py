import pytest
from typing import Any, cast

from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict import (
    CompressedDict,
)
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
    CompressedDictStorageType,
)


class TestCompressedDict:
    def test_init_empty(self) -> None:
        """Test initialization with no initial data"""
        cd: CompressedDict[str, Any] = CompressedDict(
            storage_mode=CompressedDictStorageMode(storage_type="raw"),
            properties_to_cache=[],
        )
        assert len(cd) == 0
        assert cd._storage_mode.storage_type == "raw"

    def test_init_with_dict(self) -> None:
        """Test initialization with initial dictionary"""
        initial_data = {"a": 1, "b": 2, "c": 3}
        cd = CompressedDict(
            initial_dict=initial_data,
            storage_mode=CompressedDictStorageMode(storage_type="raw"),
            properties_to_cache=[],
        )
        assert len(cd) == 3
        assert cd["a"] == 1
        assert cd["b"] == 2
        assert cd["c"] == 3

    @pytest.mark.parametrize("storage_type", ["raw", "msgpack", "compressed_msgpack"])
    def test_storage_modes(self, storage_type: CompressedDictStorageType) -> None:
        """Test different storage modes"""
        initial_data = {"key": "value"}
        cd = CompressedDict(
            initial_dict=initial_data,
            storage_mode=CompressedDictStorageMode(storage_type=storage_type),
            properties_to_cache=[],
        )
        assert cd._storage_mode.storage_type == storage_type
        with cd.transaction():
            assert cd["key"] == "value"

    def test_setitem_and_getitem(self) -> None:
        """Test setting and getting items"""
        cd: CompressedDict[str, Any] = CompressedDict(
            storage_mode=CompressedDictStorageMode(storage_type="compressed_msgpack"),
            properties_to_cache=[],
        )
        with cd.transaction():
            cd["key1"] = "value1"
            cd["key2"] = 42
            cd["key3"] = {"nested": "dict"}

        with cd.transaction():
            assert cd["key1"] == "value1"
            assert cd["key2"] == 42
            assert cd["key3"] == {"nested": "dict"}

    def test_delitem(self) -> None:
        """Test deleting items"""
        cd = CompressedDict(
            initial_dict={"a": 1, "b": 2},
            storage_mode=CompressedDictStorageMode(storage_type="compressed_msgpack"),
            properties_to_cache=[],
        )
        with cd.transaction():
            del cd["a"]

        with cd.transaction():
            assert len(cd) == 1

        with cd.transaction():
            assert not cd.__contains__("a")
            assert "a" not in cd
            assert "b" in cd

    def test_contains(self) -> None:
        """Test key existence checks"""
        cd = CompressedDict(
            initial_dict={"a": 1, "b": 2},
            storage_mode=CompressedDictStorageMode(),
            properties_to_cache=[],
        )

        with cd.transaction():
            assert "a" in cd
            assert "b" in cd
            assert "c" not in cd

    def test_keys_and_values(self) -> None:
        """Test keys and values methods"""
        initial_data = {"a": 1, "b": 2, "c": 3}
        cd: CompressedDict[str, int] = CompressedDict(
            initial_dict=initial_data,
            storage_mode=CompressedDictStorageMode(),
            properties_to_cache=[],
        )

        with cd.transaction():
            assert set(cd.keys()) == {"a", "b", "c"}
            assert set(cd.values()) == {1, 2, 3}

    def test_items(self) -> None:
        """Test items method"""
        initial_data = {"a": 1, "b": 2, "c": 3}
        cd = CompressedDict(
            initial_dict=initial_data,
            storage_mode=CompressedDictStorageMode(),
            properties_to_cache=[],
        )

        with cd.transaction():
            assert set(cd.items()) == {("a", 1), ("b", 2), ("c", 3)}

    def test_get_method(self) -> None:
        """Test get method with default"""
        cd: CompressedDict[str, Any] = CompressedDict(
            initial_dict={"a": 1},
            storage_mode=CompressedDictStorageMode(),
            properties_to_cache=[],
        )
        with cd.transaction():
            assert cd.get("a") == 1
            assert cd.get("b") is None
            assert cd.get("b", "default") == "default"

    def test_to_dict(self) -> None:
        """Test conversion to standard dictionary"""
        initial_data = {"a": 1, "b": 2}
        cd = CompressedDict(
            initial_dict=initial_data,
            storage_mode=CompressedDictStorageMode(),
            properties_to_cache=[],
        )

        with cd.transaction():
            assert cd.to_dict() == initial_data

    def test_complex_nested_structures(self) -> None:
        """Test storage of complex nested structures"""
        complex_data = {
            "nested_dict": {"inner_key": "inner_value"},
            "list": [1, 2, 3],
            "mixed": [{"a": 1}, 2, "three"],
        }

        # Test each storage storage_type
        for storage_type in ["raw", "msgpack", "compressed_msgpack"]:
            cd = CompressedDict(
                initial_dict=complex_data,
                storage_mode=CompressedDictStorageMode(
                    storage_type=cast(CompressedDictStorageType, storage_type)
                ),
                properties_to_cache=[],
            )
            with cd.transaction():
                assert cd["nested_dict"] == {"inner_key": "inner_value"}
                assert cd["list"] == [1, 2, 3]
                assert cd["mixed"] == [{"a": 1}, 2, "three"]

    def test_repr(self) -> None:
        """Test string representation"""
        cd = CompressedDict(
            initial_dict={"a": 1, "b": 2},
            storage_mode=CompressedDictStorageMode(),
            properties_to_cache=[],
        )
        repr_str = repr(cd)

        assert repr_str == "CompressedDict(storage_type='compressed_msgpack', items=2)"

    def test_error_handling(self) -> None:
        """Test error scenarios"""
        cd: CompressedDict[str, Any] = CompressedDict(
            storage_mode=CompressedDictStorageMode(), properties_to_cache=[]
        )

        # Test KeyError
        with pytest.raises(KeyError):
            with cd.transaction():
                _ = cd["non_existent_key"]

    @pytest.mark.parametrize("storage_type", ["raw", "msgpack", "compressed_msgpack"])
    def test_large_data_handling(self, storage_type: CompressedDictStorageType) -> None:
        """Test handling of large datasets"""
        large_data = {f"key_{i}": f"value_{i}" for i in range(1000)}

        cd = CompressedDict(
            initial_dict=large_data,
            storage_mode=CompressedDictStorageMode(storage_type=storage_type),
            properties_to_cache=[],
        )

        assert len(cd) == 1000
        with cd.transaction():
            assert cd["key_500"] == "value_500"
