import threading
from typing import Dict, Any


class FhirClientLogger:
    @staticmethod
    def get_variables_to_log(vars_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Method to return the variables which we need to log


        :param vars_dict: (dict) dictionary of variables names with their values
        :return: (dict) dictionary of variables names with their values
        """
        variables_to_log = {}
        for key, value in vars_dict.items():
            if not value or (
                not callable(value)
                and not isinstance(value, type(threading.Lock))
                and not str(type(value)) == "<class '_thread.lock'>"
            ):
                variables_to_log[key] = value
        variables_to_log.pop("_access_token", None)
        variables_to_log.pop("_access_token_expiry_date", None)
        variables_to_log.pop("_login_token", None)
        return variables_to_log
