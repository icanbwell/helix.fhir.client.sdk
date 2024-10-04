from typing import List, Any, Dict, Union


class DictionaryParser:
    def __init__(self) -> None:
        pass

    @staticmethod
    def flatten(my_list: List[Any]) -> List[Any]:
        """

        :param my_list:
        :return:
        """
        if not my_list:
            return my_list
        flat_list: List[Any] = []
        for element in my_list:
            if isinstance(element, list):
                flat_list.extend(DictionaryParser.flatten(element))
            else:
                flat_list.append(element)
        return flat_list

    @staticmethod
    def get_nested_property(
        parent: Dict[str, Any], path: str
    ) -> Union[List[Dict[str, Any]], Dict[str, Any], str, None]:
        """
        Iterate through each part of the path.
        Using path to drill down into the parent dictionary, return the value(s) for the last element in path.
        The first element in path should match the first element in the parent, 2nd should match 2nd, etc in order to
        return the expected result.

        :param parent: dictionary that the path should be run against
        :param path: string representation of json field, where child fields are separated by .
                     and repeating fields are indicated by [x]
        :return: Either the values for the last element of the path, a dictionary of key/value pairs, or a list of those dictionaries
        """

        if parent is None:
            return None

        parts: List[str] = path.split(".")
        result: Union[List[Dict[str, Any]], Dict[str, Any], None] = parent

        for part in parts:
            # tried a .get earlier, and it was None - exit function
            if result is None:
                return None

            # part is looking for a repeating field and result is currently a list
            # so result has one or more values that we want to return or process further.
            # Iterate through the list, try a .get(part) on each iteration for part (remove the [x] first),
            # and create a new list of the values in result
            elif part.endswith("[x]") and isinstance(result, list):
                result = [
                    value
                    for result_entry in result
                    if (value := result_entry.get(part[:-3]))
                ]

            # part is looking for a repeating field, but result is currently a dict.
            # We have gotten a part of the dictionary that we want to return.
            # Try a .get(part) on result, removing the [x] first
            elif part.endswith("[x]") and isinstance(result, dict):
                result = result.get(part[:-3], None)

            # part is not looking for a repeating field, but result is currently a list
            # iterate through result and create a new flattened list of values where
            # a .get(path) returns a value on a given iteration
            elif isinstance(result, list):
                result = DictionaryParser.flatten(
                    [
                        DictionaryParser.get_nested_property(parent=r, path=part)
                        for r in result
                        if r is not None
                    ]
                )
            else:
                # if we get here, part should be the key for the value we want to return in result
                result = result.get(part, None)

        return result
