"""Task-local suppression of third-party diagnostics carrying private internals.

Filters are installed lazily, not at import. Other requests retain their logs;
no global logger levels, handlers, or record factory are changed.
"""

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

_private = ContextVar("syntx_private_diagnostics", default=False)


class _PrivateFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not _private.get()


_filter = _PrivateFilter()


@contextmanager
def private_diagnostics():
    names = {
        "httpx",
        "filelock",
        "httpcore.connection",
        "httpcore.http11",
        "httpcore.http2",
        "httpcore.proxy",
        "httpcore.socks",
    }
    names.update(
        name
        for name in list(logging.Logger.manager.loggerDict)
        if name.startswith(("httpcore.", "httpx.", "filelock."))
    )
    for name in names:
        logger = logging.getLogger(name)
        if _filter not in logger.filters:
            logger.addFilter(_filter)
    token = _private.set(True)
    try:
        yield
    finally:
        _private.reset(token)


def private_async(function):
    @wraps(function)
    async def wrapped(*args, **kwargs):
        with private_diagnostics():
            return await function(*args, **kwargs)

    return wrapped
