class SortField:
    def __init__(self, field: str, ascending: bool = True) -> None:
        """
        Captures a field to sort by


        :param field: name of field
        :param ascending: whether to sort ascending
        """
        assert field
        assert ascending
        self.field: str = field
        self.ascending: bool = ascending

    def __str__(self) -> str:
        return self.field if self.ascending else f"-{self.field}"
