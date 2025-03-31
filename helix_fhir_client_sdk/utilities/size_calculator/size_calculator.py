import sys
from typing import Any, Optional, Set


def get_recursive_size(obj: Any, seen: Optional[Set[int]] = None) -> int:
    """
    Recursively calculate the true memory size of an object.

    Args:
        obj: Object to measure
        seen: Set of object ids already measured to prevent circular references

    Returns:
        Total memory size in bytes
    """
    # Initialize seen set if not provided
    if seen is None:
        seen = set()

    # Get object's unique id
    obj_id = id(obj)

    # Prevent infinite recursion with circular references
    if obj_id in seen:
        return 0
    seen.add(obj_id)

    # Base size calculation
    size = sys.getsizeof(obj)

    # Handle different types of objects
    if hasattr(obj, "__dict__"):
        # Add size of object's __dict__
        size += get_recursive_size(obj.__dict__, seen)

    # Handle containers and iterables
    if isinstance(obj, (str, bytes, int, float)):
        # Primitive types, no further recursion needed
        return size

    # Recursively calculate size for container types
    if isinstance(obj, (tuple, list, set, frozenset)):
        size += sum(get_recursive_size(item, seen) for item in obj)

    # Handle dictionaries
    elif isinstance(obj, dict):
        size += sum(
            get_recursive_size(k, seen) + get_recursive_size(v, seen)
            for k, v in obj.items()
        )

    # Handle custom objects
    elif hasattr(obj, "__slots__"):
        # For classes with __slots__
        for slot_name in obj.__class__.__slots__:
            if hasattr(obj, slot_name):
                slot_value = getattr(obj, slot_name)
                size += get_recursive_size(slot_value, seen)

    # Handle custom objects with instance variables
    elif hasattr(obj, "__class__"):
        # Recursively get size of instance variables
        for attr_name in dir(obj):
            # Skip methods and special attributes
            if not attr_name.startswith("__") and not callable(getattr(obj, attr_name)):
                try:
                    attr_value = getattr(obj, attr_name)
                    size += get_recursive_size(attr_value, seen)
                except Exception:
                    # Skip if attribute cannot be accessed
                    pass

    return size
