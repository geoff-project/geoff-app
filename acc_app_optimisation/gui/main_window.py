"""Definition of the main window for the app."""

import typing as t
from logging import getLogger

import pjlsa
from accwidgets.app_frame import ApplicationFrame
from accwidgets.log_console import LogConsole, LogConsoleDock, LogConsoleModel
from accwidgets.rbac import RbaToken
from accwidgets.timing_bar import TimingBarDomain
from cernml import coi
from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import Qt

from .control_pane import ControlPane
from .plot_manager import PlotManager
from .popout_mdi_area import PopoutMdiArea

LOG = getLogger(__name__)


def translate_machine(machine: coi.Machine) -> t.Optional[TimingBarDomain]:
    """Fetch the timing domain for a given CERN machine."""
    return {
        coi.Machine.LINAC_2: TimingBarDomain.PSB,
        coi.Machine.LINAC_3: TimingBarDomain.LEI,
        coi.Machine.LINAC_4: TimingBarDomain.PSB,
        coi.Machine.LEIR: TimingBarDomain.LEI,
        coi.Machine.PS: TimingBarDomain.CPS,
        coi.Machine.PSB: TimingBarDomain.PSB,
        coi.Machine.SPS: TimingBarDomain.SPS,
        coi.Machine.LHC: TimingBarDomain.LHC,
    }.get(machine)


class DumbDockWidget(QtWidgets.QDockWidget):
    """A dock widget with no special behavior whatsoever.

    The dock is not floatable. It is not closable. It has no title bar.
    It just provides a nice sidebar for the main window.
    """

    def __init__(
        self, parent: t.Optional[QtWidgets.QWidget] = None, **kwargs: t.Any
    ) -> None:
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
        QtWidgets.QAction(  # type: ignore
            "&Windows",
            parent=view_mode_group,
            checkable=True,
            checked=view_mode == QtWidgets.QMdiArea.SubWindowView,
            triggered=lambda: self._on_change_view(QtWidgets.QMdiArea.SubWindowView),
        )
        QtWidgets.QAction(  # type: ignore
            "&Tabs",
            parent=view_mode_group,
            checkable=True,
            checked=view_mode == QtWidgets.QMdiArea.TabbedView,
            triggered=lambda: self._on_change_view(QtWidgets.QMdiArea.TabbedView),
        )

        self._arrange_group = QtWidgets.QActionGroup(self)
        self._arrange_group.setEnabled(view_mode == QtWidgets.QMdiArea.SubWindowView)
        QtWidgets.QAction(  # type: ignore
            "&Cascade windows",
            parent=self._arrange_group,
            triggered=mdi_area.cascadeSubWindows,
        )
        QtWidgets.QAction(  # type: ignore
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


class MainMdiArea(PopoutMdiArea):
    """Subclass of `PopoutMdiArea` for customization."""

    def __init__(self, parent: t.Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setViewMode(QtWidgets.QMdiArea.TabbedView)
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Plain)
        self.setTabsMovable(True)

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
        self.setActiveSubWindow(first_window)  # type: ignore


class MainWindow(ApplicationFrame):
    """The main window."""

    def __init__(
        self,
        *,
        initial_machine: coi.Machine,
        lsa: pjlsa.LSAClient,
        model: t.Optional[LogConsoleModel] = None,
        japc_no_set: bool = False,
    ) -> None:
        super().__init__(use_timing_bar=True, use_rbac=True)
        mdi = MainMdiArea()
        self.setCentralWidget(mdi)
        self._plot_manager = PlotManager(mdi)
        self.runner = None

        toolbar = self.main_toolbar()
        toolbar.setAllowedAreas(Qt.TopToolBarArea)

        self.rba_widget.loginSucceeded.connect(self._on_rba_login)
        self.rba_widget.loginFailed.connect(
            lambda error: LOG.error("RBAC error: %s", error)
        )
        self.rba_widget.logoutFinished.connect(self._on_rba_logout)

        self._control_pane = ControlPane(
            initial_machine=initial_machine,
            lsa=lsa,
            plot_manager=self._plot_manager,
            japc_no_set=japc_no_set,
        )
        dock = DumbDockWidget()
        dock.setWidget(self._control_pane)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

        self._control_pane.machine_combo.currentTextChanged.connect(
            self._on_machine_changed
        )
        LOG.info("Setting up timing bar, which uses its own PyJapc instance")
        self._on_machine_changed(self._control_pane.machine_combo.currentText())

        console = LogConsole(model=model)
        console.expanded = False
        log_dock = LogConsoleDock(
            console=console, allowed_areas=Qt.BottomDockWidgetArea
        )
        log_dock.setFeatures(log_dock.DockWidgetFloatable)
        # Attach the dock to the window via ApplicationFrame.
        self.log_console = log_dock

        # We must keep ownership of this QMenu to keep the GC from
        # reclaiming it.
        self._view_menu = MdiViewMenu("&View", mdi)
        menubar = QtWidgets.QMenuBar(self)
        menubar.addMenu(self._view_menu)
        self.setMenuBar(menubar)

    def _on_machine_changed(self, value: str) -> None:
        machine = coi.Machine(value)
        timing_domain = translate_machine(machine)
        if timing_domain is not None:
            self.useTimingBar = True
            self.timing_bar.model.domain = timing_domain
        else:
            self.useTimingBar = False

    def _on_rba_login(self, token: RbaToken) -> None:
        self._control_pane.rbac_login(token)

    def _on_rba_logout(self) -> None:
        self._control_pane.rbac_logout()
