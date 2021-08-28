class BaseFilter:
    pass

    def __str__(self) -> str:
        """
        Returns the query parameter representation to send to the FHIR server
        """
        raise NotImplementedError
