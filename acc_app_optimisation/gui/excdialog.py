"""Provide a dialog for configuring optimization problems."""

import traceback
import typing as t

from PyQt5.QtCore import Qt
from PyQt5 import QtWidgets


def exception_dialog(
    exception: Exception,
    title: str,
    text: str,
    parent: t.Optional[QtWidgets.QWidget] = None,
) -> QtWidgets.QMessageBox:
    """Qt dialog that displays an exception and its traceback.

    Args:
        exception: The exception to display.
        title: The window title of the dialog.
        text: The message of the dialog. Should be one line or shorter.
        parent: The parent widget to attach to.
    """
    tbexc = traceback.TracebackException.from_exception(exception)
    dialog = QtWidgets.QMessageBox(
        QtWidgets.QMessageBox.Warning,
        title,
        text,
        parent=parent,
        buttons=QtWidgets.QMessageBox.Close,
        informativeText="".join(tbexc.format_exception_only()),
        detailedText="".join(tbexc.format()),
    )
    return dialog
