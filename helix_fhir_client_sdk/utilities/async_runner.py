import asyncio
import time
from typing import Coroutine, Any, TypeVar, Optional

T = TypeVar("T")


class AsyncRunner:
    @staticmethod
    def run(fn: Coroutine[Any, Any, T], timeout: Optional[float] = None) -> T:
        """
        Runs an async function but returns the result synchronously
        Similar to asyncio.run() but does not create a new event loop if one already exists

        :param fn: Coroutine
        :param timeout: Optional timeout in seconds to wait for loop to finish running
        :return: T
        """
        try:
            # print(f"Getting running loop")
            loop = asyncio.get_running_loop()
            # print(f"Got running loop")
        except RuntimeError:
            # print(f"Creating new event loop")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            if loop.is_running() and timeout is not None:
                # print(f"Loop is running so waiting for it to end")
                start_time = time.time()
                while loop.is_running():
                    current_time = time.time()
                    elapsed_time = current_time - start_time

                    if elapsed_time > timeout:
                        # print(f"Timeout {timeout} reached. Exiting loop.")
                        break

                    # print(f"Waiting for loop to end: {elapsed_time}")
                    time.sleep(1)
            # print(f"Running loop")
            result = loop.run_until_complete(fn)
            # print(f"Ran loop")
        except RuntimeError as e:
            if "This event loop is already running" in str(e):
                raise RuntimeError(
                    f"While calling {fn.__name__} there is already an event loop running."
                    "\nThis usually happens because you are calling this function"
                    " from an asynchronous context so you can't just wrap it in AsyncRunner.run()."
                    f"\nEither use `await {fn.__name__}` or"
                    " use nest_asyncio (https://github.com/erdewit/nest_asyncio)."
                )
            else:
                raise e
        return result
