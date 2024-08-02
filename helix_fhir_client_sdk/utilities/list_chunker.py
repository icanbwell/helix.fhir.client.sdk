from typing import List, Any, Generator


class ListChunker:
    # Yield successive n-sized chunks from l.
    @staticmethod
    def divide_into_chunks(
        array: List[Any], chunk_size: int
    ) -> Generator[List[str], None, None]:
        """
        Divides a list into a list of chunks


        :param array: array to divide into chunks
        :param chunk_size: size of each chunk
        :return: generator that returns a list of strings
        """
        # looping till length l
        for i in range(0, len(array), chunk_size):
            yield array[i : i + chunk_size]
