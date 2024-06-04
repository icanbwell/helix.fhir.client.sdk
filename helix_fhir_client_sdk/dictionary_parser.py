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
        if parent is None:
            return None

        parts: List[str] = path.split(".")
        result: Union[List[Dict[str, Any]], Dict[str, Any], None] = parent

        for part in parts:
            if result is None:
                return None
            elif part.endswith("[x]") and isinstance(result, list):
                result = [
                    value
                    for result_entry in result
                    if (value := result_entry.get(part[:-3]))
                ]
            elif part.endswith("[x]") and isinstance(result, dict):
                result = result.get(part[:-3], None)
            elif isinstance(result, list):
                result = DictionaryParser.flatten(
                    [
                        DictionaryParser.get_nested_property(parent=r, path=part)
                        for r in result
                        if r is not None
                    ]
                )
            else:
                result = result.get(part, None)

        return result
