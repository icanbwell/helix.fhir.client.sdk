from typing import List, Any, Generator, Optional


class ListChunker:
    @staticmethod
    def divide_into_chunks(
        array: List[Any], chunk_size: Optional[int]
    ) -> Generator[List[Any], None, None]:
        """
        Divides a list into a list of chunks
        Yield successive n-sized chunks from l.


        :param array: array to divide into chunks
        :param chunk_size: size of each chunk
        :return: generator that returns a list of strings
        """
        if not chunk_size:
            yield array
        else:
            # looping till length l
            for i in range(0, len(array), chunk_size):
                yield array[i : i + chunk_size]

    @staticmethod
    def divide_generator_into_chunks(
        generator: Generator[Any, None, None], chunk_size: Optional[int]
    ) -> Generator[List[Any], None, None]:
        """
        Divides a list into a list of chunks
        Yield successive n-sized chunks from l.


        :param generator: array to divide into chunks
        :param chunk_size: size of each chunk
        :return: generator that returns a list of strings
        """
        if not chunk_size:
            yield [g for g in generator]
        else:
            chunk = []
            for item in generator:
                chunk.append(item)
                if len(chunk) == chunk_size:
                    yield chunk
                    chunk = []
            if chunk:
                yield chunk
