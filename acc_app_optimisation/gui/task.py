"""Provide :class:`ThreadPoolTask`."""

import typing as t

from PyQt5 import QtCore


class ThreadPoolTask(QtCore.QRunnable):
    """Python function wrapper that can be submitted to `QThreadPool`.

    This is necessary to support PyQt versions <5.15. Starting with PyQt
    5.15, any Python callable can be passed to :class:`ThreadPool`,
    making this class superfluous.

    Args:
        func: The function to invoke on the worker thread.
        args: Positional arguments to pass to ``func``.
        kwargs: Keyword arguments to pass to ``func``.
    """

    def __init__(
        self, func: t.Callable[..., None], *args: t.Any, **kwargs: t.Any
    ) -> None:
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        self._func(*self._args, **self._kwargs)
