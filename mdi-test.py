#!/usr/bin/env python

"""Test application for floatable MDI windows."""

# pylint: disable = invalid-name, missing-function-docstring, missing-class-docstring

import sys
import typing as t

from PyQt5 import QtCore, QtGui, QtWidgets


class PopoutSubwindow(QtWidgets.QMdiSubWindow):
    def __init__(
        self,
        parent: t.Optional[QtWidgets.QWidget] = None,
        flags: QtCore.Qt.WindowFlags = QtCore.Qt.WindowFlags(),
        **kwargs,
    ) -> None:
        super().__init__(parent, flags, **kwargs)
        popout_action = QtWidgets.QAction(
            QtGui.QIcon.fromTheme("window-new"),
            "&Pop out",
            self,
            triggered=self.onPopout,
        )
        menu = self.systemMenu()
        close_action = menu.actions()[-1]
        menu.insertAction(close_action, popout_action)

    def setWidget(self, widget: QtWidgets.QWidget) -> None:
        super().setWidget(widget)
        if widget:
            self.setWindowTitle(widget.windowTitle())

    def _activateNextSubWindow(self) -> None:
        mdi = self.mdiArea()
        active_window = mdi and mdi.activeSubWindow()
        if self is active_window:
            mdi.activateNextSubWindow()

    def onPopout(self) -> None:
        self._activateNextSubWindow()
        window = PopinWindow(self)
        self.hide()
        window.show()
        window.activateWindow()


class PopinWindow(QtWidgets.QWidget):
    def __init__(
        self,
        subwindow: QtWidgets.QMdiSubWindow,
        flags: QtCore.Qt.WindowFlags = QtCore.Qt.WindowFlags(),
    ) -> None:
        super().__init__(
            parent=subwindow.window(),
            flags=flags | QtCore.Qt.Tool,
            windowTitle=subwindow.windowTitle(),
        )
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(subwindow.widget())
        subwindow.setWidget(None)
        mdi = subwindow.mdiArea()
        if mdi:
            mdi.removeSubWindow(subwindow)
        self._subwindow = subwindow
        self._mdi = mdi

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        widget = self.widget()
        if widget:
            self._subwindow.setWidget(widget)
            if self._mdi:
                self._mdi.addSubWindow(self._subwindow)
            self._subwindow.show()
        event.accept()

    def widget(self) -> t.Optional[QtWidgets.QWidget]:
        layout = self.layout()
        item = layout and layout.itemAt(0)
        return item and item.widget()


def print_parent_chain(widget: QtWidgets.QWidget) -> None:
    depth = 0
    while widget:
        print(depth * " ", widget, sep="")
        widget = widget.parent()
        depth += 1


class PoppableMdiArea(QtWidgets.QMdiArea):
    def addSubWindow(
        self,
        widget: QtWidgets.QWidget,
        flags: t.Union[
            QtCore.Qt.WindowFlags, QtCore.Qt.WindowType
        ] = QtCore.Qt.WindowFlags(),
    ) -> PopoutSubwindow:
        if isinstance(widget, PopoutSubwindow):
            subwindow = widget
        elif isinstance(widget, QtWidgets.QMdiSubWindow):
            subwindow = PopoutSubwindow()
            subwindow.setWidget(widget.widget())
            widget.setWidget(None)
        else:
            subwindow = PopoutSubwindow()
            subwindow.setWidget(widget)
        super().addSubWindow(subwindow, flags)
        subwindow.setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False)
        subwindow.setWindowFlag(QtCore.Qt.WindowSystemMenuHint, False)
        subwindow.setWindowFlag(QtCore.Qt.CustomizeWindowHint, True)
        return subwindow


class MainWindow(QtWidgets.QMainWindow):
    """Main window of the application."""

    def __init__(self):
        super().__init__()
        self.mdi = PoppableMdiArea()
        self.mdi.setMinimumSize(QtCore.QSize(640, 480))
        self.mdi.setTabsMovable(True)
        self.setCentralWidget(self.mdi)

        menubar = QtWidgets.QMenuBar()
        menubar.addAction("&Launch").triggered.connect(self.onLaunch)
        view_menu = menubar.addMenu("&View")
        window_or_tab = QtWidgets.QActionGroup(view_menu)
        view_menu.addAction(
            QtWidgets.QAction(
                QtGui.QIcon(),
                "&Windows",
                parent=window_or_tab,
                checkable=True,
                triggered=lambda: self.onChangeView(QtWidgets.QMdiArea.SubWindowView),
            )
        )
        view_menu.addAction(
            QtWidgets.QAction(
                QtGui.QIcon(),
                "&Tabs",
                parent=window_or_tab,
                checkable=True,
                checked=True,
                triggered=lambda: self.onChangeView(QtWidgets.QMdiArea.TabbedView),
            )
        )
        view_menu.addSeparator()
        self._arrangeWindowsGroup = arrange_windows = QtWidgets.QActionGroup(view_menu)
        view_menu.addAction(
            QtWidgets.QAction(
                QtGui.QIcon(),
                "&Cascade windows",
                parent=arrange_windows,
                triggered=self.mdi.cascadeSubWindows,
            )
        )
        view_menu.addAction(
            QtWidgets.QAction(
                QtGui.QIcon(),
                "&Tile windows",
                parent=arrange_windows,
                triggered=self.mdi.tileSubWindows,
            )
        )
        self.setMenuBar(menubar)
        self.onChangeView(QtWidgets.QMdiArea.TabbedView)

    def onChangeView(self, view_mode: QtWidgets.QMdiArea.ViewMode) -> None:
        self.mdi.setViewMode(view_mode)
        self._arrangeWindowsGroup.setEnabled(
            view_mode == QtWidgets.QMdiArea.SubWindowView
        )

    def onLaunch(self):
        print("onLaunch")
        for i in range(1, 4):
            self.mdi.addSubWindow(self._makeChild(f"Child {i}")).show()

    @staticmethod
    def _makeChild(title: str) -> QtWidgets.QWidget:
        widget = QtWidgets.QLabel(title, windowTitle=title)
        widget.setMinimumSize(QtCore.QSize(128, 128))
        return widget


def main(argv):
    """Main function. Call with `sys.argv`."""
    app = QtWidgets.QApplication(argv)
    window = MainWindow()
    window.show()
    app.exec_()


if __name__ == "__main__":
    main(sys.argv)
