from collections.abc import Generator

from helix_fhir_client_sdk.utilities.list_chunker import ListChunker


def test_divide_into_chunks() -> None:
    # Test with a normal list and a valid chunk size
    array = [1, 2, 3, 4, 5]
    chunk_size = 2
    result = list(ListChunker.divide_into_chunks(array, chunk_size))
    assert result == [[1, 2], [3, 4], [5]]

    # Test with a normal list and None as chunk size
    result = list(ListChunker.divide_into_chunks(array, None))
    assert result == [array]

    # Test with an empty list and a valid chunk size
    array = []
    result = list(ListChunker.divide_into_chunks(array, chunk_size))
    assert result == []

    # Test with an empty list and None as chunk size
    result = list(ListChunker.divide_into_chunks(array, None))
    assert result == [[]]


def test_divide_generator_into_chunks() -> None:
    # Helper function to create a generator
    def generator() -> Generator[int, None, None]:
        yield from range(1, 6)

    # Test with a normal generator and a valid chunk size
    gen = generator()
    chunk_size = 2
    result = list(ListChunker.divide_generator_into_chunks(gen, chunk_size))
    assert result == [[1, 2], [3, 4], [5]]

    # Test with a normal generator and None as chunk size
    gen = generator()
    result = list(ListChunker.divide_generator_into_chunks(gen, None))
    assert result == [[1, 2, 3, 4, 5]]

    # Test with an empty generator and a valid chunk size
    gen = (i for i in [])  # type: ignore[var-annotated]
    result = list(ListChunker.divide_generator_into_chunks(gen, chunk_size))
    assert result == []

    # Test with an empty generator and None as chunk size
    gen = (i for i in [])  # type: ignore[var-annotated]
    result = list(ListChunker.divide_generator_into_chunks(gen, None))
    assert result == [[]]
