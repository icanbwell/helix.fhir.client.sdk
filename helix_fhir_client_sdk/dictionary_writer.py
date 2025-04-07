import inspect
import json
from datetime import datetime, date
from typing import Any


def convert_dict_to_str(obj: Any) -> str:
    """
    Converts an object's attributes to a dictionary, handling various attribute storage methods.

    Args:
        obj: The object to convert to a dictionary

    Returns:
        A dictionary of the object's attributes
    """
    # Handle different attribute storage methods
    if hasattr(obj, "__dict__"):
        # Standard objects with __dict__
        instance_variables = obj.__dict__
    elif hasattr(obj, "__slots__"):
        # Objects using __slots__
        instance_variables = {
            slot: getattr(obj, slot) for slot in obj.__slots__ if hasattr(obj, slot)
        }
    else:
        # Fallback to using inspect to get object attributes
        instance_variables = {
            name: value
            for name, value in inspect.getmembers(obj)
            if not name.startswith("__") and not callable(value)
        }

    # Optional: Filter for specific types if needed
    filtered_variables = {
        k: v
        for k, v in instance_variables.items()
        if isinstance(v, (int, float, bool, str, type(None)))
    }

    def json_serial(obj1: Any) -> str:
        """JSON serializer for objects not serializable by default json code"""

        # https://stackoverflow.com/questions/11875770/how-to-overcome-datetime-datetime-not-json-serializable
        if isinstance(obj1, (datetime, date)):
            return obj1.isoformat()
        # if isinstance(obj, list):
        #     return f"[{[str(o) for o in obj]}]"
        return str(obj1)

    instance_variables_text: str = json.dumps(instance_variables, default=json_serial)
    return instance_variables_text
