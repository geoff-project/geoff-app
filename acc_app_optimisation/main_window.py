"""Definition of the main window for the app."""

import typing as t

import pjlsa
from accwidgets.log_console import LogConsole, LogConsoleDock, LogConsoleModel
from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import Qt

from acc_app_optimisation import gui as app_gui
from acc_app_optimisation.gui2 import control_pane as gui2


class DumbDockWidget(QtWidgets.QDockWidget):
    """A dock widget with no special behavior whatsoever.

    The dock is not floatable. It is not closable. It has no title bar.
    It just provides a nice sidebar for the main window.
    """

    def __init__(self, parent: t.Optional[QtWidgets.QWidget] = None, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.setFeatures(self.NoDockWidgetFeatures)
        empty_titlebar = QtWidgets.QWidget(self)
        self.setTitleBarWidget(empty_titlebar)


class MdiViewMenu(QtWidgets.QMenu):
    """A menu that allows controlling an MDI area."""

    def __init__(
        self,
        title: str,
        mdi_area: QtWidgets.QMdiArea,
        parent: t.Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(title, parent)
        self._mdi_area = mdi_area
        view_mode = mdi_area.viewMode()

        view_mode_group = QtWidgets.QActionGroup(self)
        QtWidgets.QAction(
            "&Windows",
            parent=view_mode_group,
            checkable=True,
            checked=view_mode == QtWidgets.QMdiArea.SubWindowView,
            triggered=lambda: self._on_change_view(QtWidgets.QMdiArea.SubWindowView),
        )
        QtWidgets.QAction(
            "&Tabs",
            parent=view_mode_group,
            checkable=True,
            checked=view_mode == QtWidgets.QMdiArea.TabbedView,
            triggered=lambda: self._on_change_view(QtWidgets.QMdiArea.TabbedView),
        )

        self._arrange_group = QtWidgets.QActionGroup(self)
        self._arrange_group.setEnabled(view_mode == QtWidgets.QMdiArea.SubWindowView)
        QtWidgets.QAction(
            "&Cascade windows",
            parent=self._arrange_group,
            triggered=mdi_area.cascadeSubWindows,
        )
        QtWidgets.QAction(
            "Ti&le windows",
            parent=self._arrange_group,
            triggered=mdi_area.tileSubWindows,
        )

        self.addActions(view_mode_group.actions())
        self.addSeparator()
        self.addActions(self._arrange_group.actions())

    def _on_change_view(self, view_mode: QtWidgets.QMdiArea.ViewMode) -> None:
        """Handler for switch between subwindow/tabbed view mode."""
        self._mdi_area.setViewMode(view_mode)
        self._arrange_group.setEnabled(view_mode == QtWidgets.QMdiArea.SubWindowView)


class MainMdiArea(app_gui.PopoutMdiArea):
    """Subclass of `PopoutMdiArea` for customization."""

    def __init__(self, parent: t.Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(
            parent,
            viewMode=QtWidgets.QMdiArea.TabbedView,
            frameShape=QtWidgets.QFrame.StyledPanel,
            frameShadow=QtWidgets.QFrame.Plain,
            tabsMovable=True,
        )

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        """Event handler to ensure that the first tab is selected upon startup."""
        # pylint: disable = invalid-name
        # "Spontaneous" means that the main window is currently
        # minimized and about to be restored. "Not spontaneous" means
        # that this widget is currently hidden and about to be made
        # visible. In our application, this only happens at startup,
        # when `main_window.show()` is called.
        if event.spontaneous():
            return
        # Show the first subwindow instead of the one most recently
        # created.
        windows = self.subWindowList(self.CreationOrder)
        first_window = windows[0] if windows else None
        self.setActiveSubWindow(first_window)


class MainWindow(QtWidgets.QMainWindow):
    """The main window."""

    def __init__(
        self,
        *,
        lsa: pjlsa.LSAClient,
        model: t.Optional[LogConsoleModel] = None,
    ) -> None:
        super().__init__()
        mdi = MainMdiArea()
        self.setCentralWidget(mdi)
        self._plot_manager = app_gui.PlotManager(mdi)
        self.runner = None

        self._control_pane = gui2.ControlPane(
            lsa=lsa,
            plot_manager=self._plot_manager,
        )
        dock = DumbDockWidget()
        dock.setWidget(self._control_pane)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

        console = LogConsole(model=model)
        console.expanded = False
        log_dock = LogConsoleDock(
            console=console, allowed_areas=Qt.BottomDockWidgetArea
        )
        log_dock.setFeatures(log_dock.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, log_dock)

        # We must keep ownership of this QMenu to keep the GC from
        # reclaiming it.
        self._view_menu = MdiViewMenu("&View", mdi)
        menubar = QtWidgets.QMenuBar(self)
        menubar.addMenu(self._view_menu)
        self.setMenuBar(menubar)

        # self.setStatusBar(QtWidgets.QStatusBar(self))
