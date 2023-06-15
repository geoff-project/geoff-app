# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

"""Provide a dialog for configuring optimization problems."""

import logging
import sys
import typing as t
from traceback import TracebackException

from PyQt5 import QtWidgets


class ExceptionQueue:
    """A queue to swallow exceptions during initialization and show them later."""

    def __init__(self, title: str) -> None:
        self._queue: t.Deque[t.Tuple[str, TracebackException]] = t.Deque()
        self._title = title

    def append(
        self,
        exception: BaseException,
        text: str,
        logger: t.Optional[logging.Logger] = logging.root,
    ) -> None:
        """Append an exception to the queue for later display."""
        if logger:
            logger.error(text, exc_info=exception)
        self._queue.append((text, TracebackException.from_exception(exception)))

    def show_all(self, parent: t.Optional[QtWidgets.QWidget] = None) -> None:
        """Show all exceptions as a series of dialogs."""
        if not self._queue:
            return
        text, exception = self._queue.popleft()
        remainder = len(self._queue)
        title = self._title if not remainder else f"{self._title} (+{remainder} more)"
        dialog = exception_dialog(exception, title, text, parent)
        dialog.finished.connect(lambda _res: self.show_all(parent))
        dialog.show()


def exception_dialog(
    exception: t.Union[Exception, TracebackException],
    title: str,
    text: str,
    parent: t.Optional[QtWidgets.QWidget] = None,
) -> QtWidgets.QMessageBox:
    """Qt dialog that displays an exception and its traceback.

    Args:
        exception: The exception to display. This may also be a
            :class:`~traceback.TracebackException` if you need to avoid
            holding onto references. If None is passed, this uses
            :func:`sys.exc_info()` to get the exception that is
            currently being handled.
        title: The window title of the dialog.
        text: The message of the dialog. Should be one line or shorter.
        parent: The parent widget to attach to.
    """
    if not isinstance(exception, TracebackException):
        exception = TracebackException.from_exception(exception)
    dialog = QtWidgets.QMessageBox(
        QtWidgets.QMessageBox.Warning,
        title,
        text,
        parent=parent,
        buttons=QtWidgets.QMessageBox.Close,
    )
    dialog.setInformativeText("".join(exception.format_exception_only()))
    dialog.setDetailedText("".join(exception.format()))
    return dialog


def current_exception_dialog(
    title: str, text: str, parent: t.Optional[QtWidgets.QWidget] = None
) -> QtWidgets.QMessageBox:
    """Qt dialog that displays the current exception and its traceback.

    This is like :func:`exception_dialog()` but it uses
    :func:`sys.exc_info()` to retrieve the exception that is currently
    being handled.

    Args:
        title: The window title of the dialog.
        text: The message of the dialog. Should be one line or shorter.
        parent: The parent widget to attach to.

    Raises:
        RuntimeError: if there is no exception currently in-flight.
    """
    exc_type, exc_value, exc_tb = sys.exc_info()
    if not (exc_type and exc_value and exc_tb):
        raise RuntimeError("no current exception")
    return exception_dialog(
        exception=TracebackException(exc_type, exc_value, exc_tb),
        title=title,
        text=text,
        parent=parent,
    )
