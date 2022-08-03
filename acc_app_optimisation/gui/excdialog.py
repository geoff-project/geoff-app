"""Provide a dialog for configuring optimization problems."""

import sys
import typing as t
from traceback import TracebackException

from PyQt5 import QtWidgets


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
        tbexc = TracebackException.from_exception(exception)
    dialog = QtWidgets.QMessageBox(
        QtWidgets.QMessageBox.Warning,
        title,
        text,
        parent=parent,
        buttons=QtWidgets.QMessageBox.Close,
    )
    dialog.setInformativeText("".join(tbexc.format_exception_only()))
    dialog.setDetailedText("".join(tbexc.format()))
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
