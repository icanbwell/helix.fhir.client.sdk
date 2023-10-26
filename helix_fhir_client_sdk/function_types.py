from typing import Callable, List, Dict, Any, Optional, Awaitable

HandleBatchFunction = Callable[[List[Dict[str, Any]], Optional[int]], Awaitable[bool]]
HandleStreamingChunkFunction = Callable[[bytes, Optional[int]], Awaitable[bool]]
HandleErrorFunction = Callable[[str, str, Optional[int]], Awaitable[bool]]
