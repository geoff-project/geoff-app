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

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt

__all__ = [
    "ExceptionQueue",
    "current_exception_dialog",
    "exception_dialog",
]


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
    dialog = _ExceptionMessageBox(
        QtWidgets.QMessageBox.Warning,
        title,
        text,
        parent=parent,
        buttons=QtWidgets.QMessageBox.Close,
        keywords=_gather_keywords(exception),
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


class _ExceptionMessageBox(QtWidgets.QMessageBox):
    """A message box suitable for showing exceptions.

    There are three differences in behavior from a standard message box:

    1. it is resizeable;
    2. the detailed text is shown in a monospace font;
    3. a syntax highlighter is applied to the detailed text. It
       highlights Python code location lines and the exception
       that was raised.
    """

    # pylint: disable = invalid-name
    # pylint: disable = too-many-arguments

    def __init__(
        self,
        icon: QtWidgets.QMessageBox.Icon,
        title: str,
        text: str,
        buttons: t.Union[
            QtWidgets.QMessageBox.StandardButtons,
            QtWidgets.QMessageBox.StandardButton,
        ] = QtWidgets.QMessageBox.NoButton,
        parent: t.Optional[QtWidgets.QWidget] = None,
        flags: Qt.WindowFlags = Qt.Dialog | Qt.MSWindowsFixedSizeDialogHint,
        keywords: t.Tuple[str, ...] = (),
    ) -> None:
        super().__init__(icon, title, text, buttons, parent, flags)
        self._max_size = self.maximumSize()
        self._keywords = keywords
        self._highlighter: t.Optional[QtGui.QSyntaxHighlighter] = None

    def setDetailedText(self, text: str) -> None:
        super().setDetailedText(text)
        edit = t.cast(
            t.Optional[QtWidgets.QTextEdit], self.findChild(QtWidgets.QTextEdit)
        )
        if edit:
            edit.setMaximumSize(self._max_size)
            edit.setFont(_find_monospace_font())
            edit.moveCursor(QtGui.QTextCursor.End)
            self._highlighter = _TracebackHighlighter(self._keywords, edit)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        self.setMaximumSize(self._max_size)
        return super().resizeEvent(event)


class _TracebackHighlighter(QtGui.QSyntaxHighlighter):
    """Highlight important parts of a standard Python traceback."""

    # pylint: disable = invalid-name

    def __init__(self, keywords: t.Tuple[str, ...], parent: QtCore.QObject) -> None:
        super().__init__(parent)
        self.re_location_line = QtCore.QRegularExpression(
            r"^\s+File (\".*\"), line (\d+), in ([^\s]+)$"
        )
        # Only highlight exception names at the start of the line.
        re_keywords = "^" + "|".join(map(QtCore.QRegularExpression.escape, keywords))
        self.re_keywords = (
            QtCore.QRegularExpression(re_keywords) if re_keywords else None
        )

    def highlightBlock(self, text: str) -> None:
        match = self.re_location_line.match(text)
        if match.hasMatch():
            for i, color in enumerate([Qt.darkGreen, Qt.darkGreen, Qt.blue], 1):
                self.setFormat(match.capturedStart(i), match.capturedLength(i), color)
            return
        if self.re_keywords:
            matches = self.re_keywords.globalMatch(text)
            while matches.hasNext():
                match = matches.next()
                self.setFormat(match.capturedStart(0), match.capturedLength(0), Qt.red)


def _gather_keywords(exception: t.Optional[TracebackException]) -> tuple[str, ...]:
    res = []
    for exc in _iter_exc_chain(exception):
        name = getattr(exc, "exc_type_str", None)
        if name is None:
            name = getattr(exc.exc_type, "__name__", None)
            if name is None:
                continue
        res.append(name)
    return tuple(res)


def _iter_exc_chain(
    exc: t.Optional[TracebackException],
) -> t.Iterator[TracebackException]:
    """Iterate through the names of all types in the given exception chain.

    This searches depth-first for both contexts and causes of the given
    exception.
    """
    while exc:
        yield exc
        exc = exc.__cause__ or (None if exc.__suppress_context__ else exc.__context__)


def _find_monospace_font() -> QtGui.QFont:
    """Return the default monospace font."""
    font = QtGui.QFont("monospace")
    font.setStyleHint(QtGui.QFont.Monospace)
    return font
