import inspect
from typing import Any
from unittest.mock import MagicMock

import aiohttp

# aiohttp 3.12 added stream_writer as a required kwarg to ClientResponse.__init__.
# aioresponses 0.7.x does not pass it. Patch here so tests that use aioresponses
# continue to work without downgrading aiohttp to a version with known CVEs.
_orig_clientresponse_init = aiohttp.ClientResponse.__init__
_sig_params = inspect.signature(_orig_clientresponse_init).parameters
if "stream_writer" in _sig_params and _sig_params["stream_writer"].default is inspect.Parameter.empty:

    def _patched_clientresponse_init(
        self: aiohttp.ClientResponse,
        *args: Any,
        stream_writer: Any = None,
        **kwargs: Any,
    ) -> None:
        _orig_clientresponse_init(self, *args, stream_writer=stream_writer or MagicMock(), **kwargs)

    aiohttp.ClientResponse.__init__ = _patched_clientresponse_init  # type: ignore[method-assign]
