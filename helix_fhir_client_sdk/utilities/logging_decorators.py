import functools
import logging

logging.basicConfig(level=logging.INFO, format='[SDK] %(message)s', force=True)

def log_execution_time(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        func_name = func.__qualname__
        import time
        start_time = time.time()
        logger.info(f"[START] {func_name}")
        result = await func(*args, **kwargs)
        end_time = time.time()
        logger.info(f"[END] {func_name} - Duration: {end_time - start_time:.3f}s")
        return result
    return wrapper

def log_execution_time_sync(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        func_name = func.__qualname__
        import time
        start_time = time.time()
        logger.info(f"[START] {func_name}")
        result = func(*args, **kwargs)
        end_time = time.time()
        logger.info(f"[END] {func_name} - Duration: {end_time - start_time:.3f}s")
        return result
    return wrapper

def log_execution_time_asyncgen(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        func_name = func.__qualname__
        import time
        start_time = time.time()
        logger.info(f"[START] {func_name}")
        try:
            async for item in func(*args, **kwargs):
                yield item
        finally:
            end_time = time.time()
            logger.info(f"[END] {func_name} - Duration: {end_time - start_time:.3f}s")
    return wrapper

def log_execution_time_syncgen(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        func_name = func.__qualname__
        import time
        start_time = time.time()
        logger.info(f"[START] {func_name}")
        try:
            for item in func(*args, **kwargs):
                yield item
        finally:
            end_time = time.time()
            logger.info(f"[END] {func_name} - Duration: {end_time - start_time:.3f}s")
    return wrapper
