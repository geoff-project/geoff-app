#!/usr/bin/env python

"""Provide the `PopoutMdiArea` class."""

# pylint: disable = invalid-name

from typing import Optional, Union

from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import Qt


class PopoutSubwindow(QtWidgets.QMdiSubWindow):
    """A `QMdiSubWindow` that can pop out of its area."""

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        flags: Qt.WindowFlags = Qt.WindowFlags(),
        **kwargs,
    ) -> None:
        super().__init__(parent, flags, **kwargs)
        # Add "Popout" either before "Close" or as the only entry.
        icon = QtGui.QIcon.fromTheme("window-new")
        popout_action = QtWidgets.QAction(
            icon, "&Pop out", self, triggered=self._onPopout
        )
        menu = self.systemMenu()
        if menu.actions():
            close_action = menu.actions()[-1]
            menu.insertAction(close_action, popout_action)
        else:
            menu.addAction(popout_action)

    def setWidget(self, widget: QtWidgets.QWidget) -> None:
        """Change the inner widget of this subwindow.

        If the widget has a window title, this subwindow uses it as its
        own window title.
        """
        super().setWidget(widget)
        if widget:
            self.setWindowTitle(widget.windowTitle())

    def _removeFocusFromSelf(self) -> None:
        """Switch focus away from this window so that one stays focused."""
        mdi = self.mdiArea()
        active_window = mdi and mdi.activeSubWindow()
        if self is active_window:
            mdi.activateNextSubWindow()

    def _onPopout(self) -> None:
        """Handler for the Popout action."""
        self._removeFocusFromSelf()
        # Reparent the inner widget and hide self. `PopinWindow` will
        # show us once it is closed.
        self.hide()
        window = PopinWindow(self)
        window.show()
        window.activateWindow()


class PopinWindow(QtWidgets.QWidget):
    """A floating window that can be popped back into an MDI area.

    You typically don't instantiate this class yourself.
    `PopoutSubwindow` creates it when it is popped out of its MDI area.
    """

    def __init__(
        self,
        subwindow: QtWidgets.QMdiSubWindow,
        flags: Qt.WindowFlags = Qt.WindowFlags(),
    ) -> None:
        super().__init__(
            parent=subwindow.window(),
            flags=flags | Qt.Tool,
            windowTitle=subwindow.windowTitle(),
        )
        # Emulate behavior of widgets like `QMdiSubWindow` that contain
        # one and only one "inner widget".
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # Steal the inner widget.
        if subwindow.widget():
            layout.addWidget(subwindow.widget())
            subwindow.setWidget(None)
        # Detach the subwindow from its MDI area, but remember both.
        mdi = subwindow.mdiArea()
        if mdi:
            mdi.removeSubWindow(subwindow)
        self._subwindow = subwindow
        self._mdi = mdi

    def mdiArea(self) -> QtWidgets.QMdiArea:
        """Return the MDI area that this window will return to."""
        return self._mdi

    def setMdiArea(self, mdi: Optional[QtWidgets.QMdiArea]) -> None:
        """Set the MDI area that this window will return to.

        If set to None, this window will not return anywhere. Closing it
        actually closes the window permanently.
        """
        self._mdi = mdi

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Upon close, reattach the subwindow to its MDI area."""
        widget = self.widget()
        if widget:
            self._subwindow.setWidget(widget)
            if self._mdi:
                self._mdi.addSubWindow(self._subwindow)
                self._subwindow.show()
            else:
                self._subwindow.close()
        event.accept()

    def widget(self) -> Optional[QtWidgets.QWidget]:
        """Return the inner widget managed by this window."""
        item = self.layout().itemAt(0)
        return item and item.widget()

    def setWidget(self, widget: Optional[QtWidgets.QWidget]) -> None:
        """Replace the inner widget with a given one.

        Passing None removes the inner widget. If there already is an
        inner widget, it is removed, but not deleted. You have to do
        that yourself, e.g. via `widget.deleteLater()`.
        """
        layout = self.layout()
        # Remove all children.
        while layout.count():
            old_widget = layout.takeAt(0).widget()
            if old_widget:
                old_widget.setParent(None)
        # Re-add the given widget if there is one.
        if widget:
            layout.addWidget(widget)


class PopoutMdiArea(QtWidgets.QMdiArea):
    """An MDI area whose subwindows may be popped out of the window.

    Subwindows are usually clipped to and confined by the MDI area
    itself. Each subwindow made by this area has an menu entry that
    allows to "pop" it out.

    Such a window becomes a child of the MDI area's parent window and
    can float outside of it. Closing such a free window re-attaches it
    to the MDI area.
    """

    def addSubWindow(
        self,
        widget: QtWidgets.QWidget,
        flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.WindowFlags(),
    ) -> PopoutSubwindow:
        """Add `widget` as a new subwindow to the MDI area.

        If `flags` is passed, it overrides the default. Contrary to
        regular MDI areas, this one makes its subwindows non-closable by
        default.

        If `widget` is a `PopoutSubwindow`, it is attached directly. If
        it is any other `QMdiSubWindow`, its inner widget is stolen by a
        new `PopoutSubwindow`. If it is any other widget, a new
        `PopoutSubwindow` is created and `widget` is added as its
        internal widget.

        When you create your own subwindow, you must set the
        `WA_DeleteOnClose` widget attribute if you want the window to be
        deleted when closed in the MDI area. If not, the window will be
        hidden and the MDI area will not activate the next subwindow

        In any case, the return value is the `PopoutSubwindow` that has
        been added.
        """
        if isinstance(widget, PopoutSubwindow):
            subwindow = widget
        elif isinstance(widget, QtWidgets.QMdiSubWindow):
            subwindow = PopoutSubwindow()
            subwindow.setAttribute(Qt.WA_DeleteOnClose, True)
            subwindow.setWidget(widget.widget())
            widget.setWidget(None)
        else:
            subwindow = PopoutSubwindow()
            subwindow.setAttribute(Qt.WA_DeleteOnClose, True)
            subwindow.setWidget(widget)
        super().addSubWindow(subwindow, flags)
        if not flags:
            subwindow.setWindowFlag(Qt.WindowCloseButtonHint, False)
            subwindow.setWindowFlag(Qt.WindowSystemMenuHint, False)
            subwindow.setWindowFlag(Qt.CustomizeWindowHint, True)
        return subwindow

    def removePopinWindow(self, window: PopinWindow) -> None:
        """Detach a pop-in window from this MDI area.

        A detached window will, when closed, no longer return to the MDI
        area. Instead, it will actually close.
        """
        if self is window.mdiArea():
            window.setMdiArea(None)
