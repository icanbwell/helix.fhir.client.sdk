import asyncio
from typing import Coroutine, Any, TypeVar

T = TypeVar("T")


class AsyncRunner:
    @staticmethod
    def run(fn: Coroutine[Any, Any, T]) -> T:
        """
        Runs an async function but returns the result synchronously
        Similar to asyncio.run() but does not create a new event loop if one already exists

        :param fn: Coroutine
        :return: T
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(fn)
        return result
