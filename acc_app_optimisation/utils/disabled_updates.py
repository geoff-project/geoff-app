"""Provide the context manager `disabled_updates()."""

from contextlib import contextmanager
from typing import Iterator, TypeVar

from PyQt5.QtWidgets import QWidget

__all__ = ["disabled_updates"]

W = TypeVar("W", bound=QWidget)


@contextmanager
def disabled_updates(widget: W) -> Iterator[W]:
    """Temporarily disable painting for the given widget.

    Example:

        >>> w = QWidget()
        >>> assert w.updatesEnabled()
        >>> with disabled_updates(w) as w_inner:
        ...     assert w_inner is w
        ...     assert not w.updatesEnabled()
        ... assert w.updatesEnabled()
    """
    old_state = widget.updatesEnabled()
    widget.setUpdatesEnabled(False)
    try:
        yield widget
    finally:
        widget.setUpdatesEnabled(old_state)
