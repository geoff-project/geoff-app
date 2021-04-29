"""Provide the :class:`FileSelector` widget.
"""
import os
import typing as t

from PyQt5 import QtCore, QtWidgets


class FileSelector(QtWidgets.QWidget):
    """A widget shows the most-recent result of a load-file dialog.

    Conceptually, this widget is a read-only line edit with a tool
    button attached. The tool button opens a load-file dialog. Every
    time the dialog is accepted, the line edit is updated with the
    selected file path.

    Args:
        path: The initially selected file. If not passed, the widget
            starts out empty.
        parent: The parent widget, if any.

    Keyword args:
        directory: The initial directory for the load-file dialog. If
            not passed, this is the user's home directory.
        mimeTypeFilters: A list of MIME types selectable in the
            load-file dialog.
        nameFilters: A list of name filters selectable in the load-file
            dialog.

    All further keyword arguments are forwarded to the :class:`QWidget`
    constructor.

    Signals:
        fileSelected: This signal is emitted every time the load-file
            dialog is accepted.
        fileChanged: This signal is emitted every time the currently
            selected file changes. This can happen through the load-file
            dialog or through :meth:`setFilePath()`.
    """

    # pylint: disable = invalid-name

    fileSelected = QtCore.pyqtSignal(str)
    fileChanged = QtCore.pyqtSignal(str)

    def __init__(
        self,
        path: t.Union[None, str, bytes, os.PathLike] = None,
        parent: t.Optional[QtWidgets.QWidget] = None,
        *,
        dialogDirectory: t.Union[None, str, bytes, os.PathLike, QtCore.QDir] = None,
        mimeTypeFilters: t.Optional[t.Iterable[str]] = None,
        nameFilters: t.Optional[t.Iterable[str]] = None,
        **kwargs: t.Any,
    ) -> None:
        super().__init__(parent, **kwargs)
        self._dialog = QtWidgets.QFileDialog(self.window())
        self._dialog.setAcceptMode(self._dialog.AcceptOpen)
        self._dialog.setFileMode(self._dialog.ExistingFile)
        self._dialog.setModal(True)
        self._dialog.accepted.connect(self._update_edit_from_dialog)
        self._edit = QtWidgets.QLineEdit("")
        self._edit.setReadOnly(True)
        self._edit.textChanged.connect(self.fileChanged)
        self._open = QtWidgets.QAction("…")
        self._open.triggered.connect(self.showFileDialog)
        self._button = QtWidgets.QToolButton()
        self._button.setDefaultAction(self._open)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._edit)
        layout.addWidget(self._button)
        if dialogDirectory is not None:
            self.setDialogDirectory(dialogDirectory)
        if mimeTypeFilters is not None and nameFilters is not None:
            raise TypeError("conflicting arguments: nameFilters and mimeTypeFilters")
        if mimeTypeFilters is not None:
            self.setMimeTypeFilters(mimeTypeFilters)
        if nameFilters is not None:
            self.setNameFilters(nameFilters)
        if path is not None:
            self.setFilePath(path)
            self._dialog.selectFile(self.filePath())

    def showFileDialog(self) -> None:
        """Show the load-file dialog."""
        self._dialog.show()

    def nameFilters(self) -> t.List[str]:
        """Return the file type filters used in the dialog."""
        return self._dialog.nameFilters()

    def setNameFilter(self, filter_: str) -> None:
        """Set the file type filter used in the dialog.

        If filter contains a pair of parentheses containing one or more
        filename-wildcard patterns, separated by spaces, then only the
        text contained in the parentheses is used as the filter. This
        means that these calls are all equivalent::

            w.setNameFilter("C++ files (*.cpp *.cc *.C *.cxx *.c++)")
            w.setNameFilter("*.cpp *.cc *.C *.cxx *.c++")

        If you want to use multiple filters, separate each one with two
        semicolons. For example::

            "Images (*.png);;Text files (*.txt);;XML files (*.xml)"

        Note that the filter ``*.*`` is not portable, because the
        historical assumption that the file extension determines the
        file type is not consistent on every operating system. It is
        possible to have a file with no dot in its name (for example,
        Makefile). In a native Windows file dialog, ``*.*`` will match
        such files, while in other types of file dialogs it may not. So
        it is better to use ``*`` if you mean to select any file.

        You may also use :meth:`setNameFilters()` to set multiple
        filters.
        """
        self._dialog.setNameFilter(filter_)

    def setNameFilters(self, filters: t.Iterable[str]) -> None:
        """Set the filters used in the file dialog."""
        self._dialog.setNameFilters(filters)

    def setMimeTypeFilters(self, filters: t.Iterable[str]) -> None:
        """Set the dialog's file type filters from a list of MIME types.

        Convenience method for :meth:`setNameFilters()`. Uses
        :class:`QMimeType` to create a name filter from the glob
        patterns and description defined in each MIME type.

        Use ``application/octet-stream`` for the “All files (*)” filter,
        since that is the base MIME type for all files.

        Calling overrides any previously set name filters, and changes
        the return value of :meth:`nameFilters()`.

        Example::

            w = FileSelector()
            w.setMimeTypeFilters([
                "image/jpeg",
                "image/png",
                "application/octet-stream",
            ])
            # Will show the following filters:
            # JPEG image (*.jpeg *.jpg *.jpe)
            # PNG image (*.png)
            # All files (*)
            w.showFileDialog()
        """
        self._dialog.setMimeTypeFilters(filters)

    def dialogDirectory(self) -> QtCore.QDir:
        """Return the directory currently displayed in the dialog."""
        return self._dialog.directory()

    def setDialogDirectory(
        self, directory: t.Union[str, bytes, os.PathLike, QtCore.QDir]
    ) -> None:
        """Set the directory currently displayed in the dialog."""
        if isinstance(directory, QtCore.QDir):
            self._dialog.setDirectory(directory)
        else:
            self._dialog.setDirectory(os.fsdecode(directory))

    def filePath(self) -> str:
        """Return the currently selected file."""
        return self._edit.text()

    def setFilePath(self, path: t.Union[str, bytes, os.PathLike]) -> None:
        """Set the currently selected file."""
        self._edit.setText(os.fsdecode(path))

    def _update_edit_from_dialog(self) -> None:
        paths = self._dialog.selectedFiles()
        assert len(paths) == 1, paths
        [path] = paths
        self._edit.setText(path)
        self.fileSelected.emit(path)
