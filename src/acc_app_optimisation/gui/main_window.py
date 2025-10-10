# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

"""Definition of the main window for the app."""

import typing as t
from logging import getLogger

import jpype
import pjlsa
import pyjapc
import pyrbac
from accwidgets.app_frame import ApplicationFrame
from accwidgets.log_console import LogConsole, LogConsoleDock, LogConsoleModel
from accwidgets.timing_bar import TimingBar
from cernml import coi
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt

from .. import translate
from ..lsa_utils_hooks import GeoffHooks
from .control_pane import ControlPane
from .plot_manager import PlotManager
from .popout_mdi_area import PopoutMdiArea

if t.TYPE_CHECKING:
    from pylogbook.models import Activity

LOG = getLogger(__name__)


def get_lsa_server(lsa: pjlsa.LSAClient) -> str:
    """Query the selected LSA server."""
    # We don't actually read anything from the LSAClient instance. We
    # just take it as proof that the user has already initialized LSA
    # (and so the lsa.server property _must_ be set).
    if not isinstance(lsa, pjlsa.LSAClient):
        raise TypeError(f"not an LSAClient: {lsa!r}")
    java_lang = jpype.JPackage("java.lang")
    server_name = java_lang.System.getProperty("lsa.server")
    if not isinstance(server_name, str):
        raise TypeError(f"lsa.server is not a string: {server_name!r}")
    return server_name


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
        self._arrange_group.setEnabled(True)
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
        self.setViewMode(QtWidgets.QMdiArea.SubWindowView)
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Plain)
        self.setTabsMovable(True)

    def arrange_windows_on_startup(
        self,
        obj_cons_window: QtWidgets.QMdiSubWindow,
        actors_window: QtWidgets.QMdiSubWindow,
        rl_window: QtWidgets.QMdiSubWindow,
    ) -> None:
        """Arrange the default windows: tile actors and obj/cons vertically, minimize RL."""
        # Get the available area for arranging windows
        mdi_rect = self.viewport().rect()
        width = mdi_rect.width()
        height = mdi_rect.height()

        # Split the height in half for the two visible windows
        half_height = height // 2

        # Actors on top - ensure it's shown normally first
        actors_window.showNormal()
        actors_window.setGeometry(0, 0, width, half_height)

        # Objective and Constraints on bottom - ensure it's shown normally first
        obj_cons_window.showNormal()
        obj_cons_window.setGeometry(0, half_height, width, half_height)

        # Minimize the RL Training window since it's rarely used
        # showMinimized will show it as an icon in the MDI area
        rl_window.showMinimized()

        # Activate the actors window
        self.setActiveSubWindow(actors_window)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        """Event handler to arrange windows on startup."""
        # pylint: disable = invalid-name
        # "Spontaneous" means that the main window is currently
        # minimized and about to be restored. "Not spontaneous" means
        # that this widget is currently hidden and about to be made
        # visible. In our application, this only happens at startup,
        # when `main_window.show()` is called.
        if event.spontaneous():
            return
        # The arrangement will be done by MainWindow after PlotManager is created
        pass


class MainWindow(ApplicationFrame):
    """The main window."""

    # pylint: disable=invalid-name

    def __init__(
        self,
        *,
        version: str,
        japc: pyjapc.PyJapc,
        lsa: pjlsa.LSAClient,
        lsa_hooks: GeoffHooks,
        model: t.Optional[LogConsoleModel] = None,
    ) -> None:
        super().__init__(use_timing_bar=True, use_rbac=True, use_screenshot=True)
        self.appVersion = version  # type: ignore # mypy bug #9911

        self._mdi = MainMdiArea()
        self.setCentralWidget(self._mdi)
        self._plot_manager = PlotManager(self._mdi)
        self.runner = None
        self._windows_arranged = False

        toolbar = self.main_toolbar()
        toolbar.setAllowedAreas(Qt.TopToolBarArea)

        assert self.timing_bar is not None, "we passed use_timing_bar=True"
        self.timing_bar.indicateHeartbeat = False
        self.timing_bar.highlightedUser = ""

        assert self.rba_widget is not None, "we passed use_rbac=True"
        self.rba_widget.loginSucceeded.connect(self._on_rba_login)
        self.rba_widget.logoutFinished.connect(self._on_rba_logout)
        self.rba_widget.loginFailed.connect(
            lambda error: LOG.error("RBAC error: %s", error)
        )
        self.rba_widget.tokenExpired.connect(
            lambda _: LOG.warning("RBAC token expired")
        )

        assert self.screenshot_widget is not None, "we passed use_screenshot=True"
        self.screenshot_widget.captureFailed.connect(
            lambda error: LOG.error("Screenshot error: %s", error)
        )
        self.screenshot_widget.eventFetchFailed.connect(
            lambda error: LOG.warning("Could not fetch Logbook event: %s", error)
        )
        self.screenshot_widget.activitiesFailed.connect(
            lambda error: LOG.warning("Could not fetch Lookbook activities: %s", error)
        )

        self._control_pane = ControlPane(
            japc=japc, lsa=lsa, lsa_hooks=lsa_hooks, plot_manager=self._plot_manager
        )
        dock = DumbDockWidget()
        dock.setWidget(self._control_pane)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

        self._control_pane.machine_combo.stableTextChanged.connect(
            self._on_machine_changed
        )
        self._control_pane.lsa_selector.userSelectionChanged.connect(
            self._on_lsa_user_changed
        )
        LOG.info("Setting up timing bar, which uses its own PyJapc instance")
        self._on_machine_changed(self._control_pane.machine_combo.currentText())

        console = LogConsole(model=model)
        console.expanded = False  # type: ignore # mypy bug #9911
        log_dock = LogConsoleDock(
            console=console,
            allowed_areas=Qt.DockWidgetAreas(Qt.BottomDockWidgetArea),
        )
        log_dock.setFeatures(log_dock.DockWidgetFloatable)
        # Attach the dock to the window via ApplicationFrame.
        self.log_console = log_dock

        # We must keep ownership of this QMenu to keep the GC from
        # reclaiming it.
        self._view_menu = MdiViewMenu("&View", mdi)
        self._view_menu.addSeparator()
        self._fullscreen_action = self._view_menu.addAction("&Fullscreen")
        self._fullscreen_action.setCheckable(True)
        self._fullscreen_action.setShortcut(QtGui.QKeySequence("F11"))
        self._fullscreen_action.triggered.connect(self.toggleFullScreen)
        menubar = self.menuBar()
        menubar.addMenu(self._view_menu)
        menubar.addAction("Info").triggered.connect(self.showAboutDialog)

        # Ordering: This may only be done once the ControlPane has been
        # created.
        LOG.info("RBAC: Attempting automatic location-based login")
        self.rba_widget.model.login_by_location(interactively_select_roles=False)

    def make_initial_selection(self, selection: translate.InitialSelection) -> None:
        """Pre-select machine and user according to command-line arguments."""
        self._control_pane.make_initial_selection(selection)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        """Arrange windows on first show."""
        super().showEvent(event)
        if not event.spontaneous() and not self._windows_arranged:
            self._windows_arranged = True
            obj_cons, actors, rl_training = self._plot_manager.get_default_subwindows()
            self._mdi.arrange_windows_on_startup(obj_cons, actors, rl_training)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        # Close events are only sent to the top-level window that gets
        # closed. Forward this one to the control pane to properly
        # invoke finalizers.
        self._control_pane.closeEvent(event)

    def changeEvent(self, event: QtCore.QEvent) -> None:
        # The window manager is able to put our window into fullscreen
        # mode without going through our "fullscreen" menu item. If this
        # happens, we need to manually update the menu item's checkbox.
        if isinstance(event, QtGui.QWindowStateChangeEvent):
            is_fullscreen = self.windowState() & Qt.WindowFullScreen  # type: ignore
            self._fullscreen_action.setChecked(bool(is_fullscreen))

    def timingBarAction(self) -> QtWidgets.QAction:
        toolbar = self.main_toolbar()
        [timing_bar_action] = (
            action
            for action in toolbar.actions()
            if isinstance(toolbar.widgetForAction(action), TimingBar)
        )
        return timing_bar_action

    def _on_machine_changed(self, value: str) -> None:
        machine = coi.Machine(value)
        assert self.screenshot_widget is not None, "we passed use_screenshot=True"
        self.screenshot_widget.model.logbook_activities = t.cast(
            # This cast circumvents the issue mypy#3004.
            t.Sequence["Activity"],
            translate.machine_to_activity(machine),
        )
        timing_domain = translate.machine_to_timing_domain(machine)
        assert self.timing_bar is not None, "we passed use_timing_bar=True"
        if timing_domain:
            self.timing_bar.model.domain = timing_domain
            self.timingBarAction().setVisible(True)
        else:
            self.timingBarAction().setVisible(False)

    def _on_lsa_user_changed(self, user_name: str) -> None:
        bare_user = user_name.rpartition(".")[-1]
        assert self.timing_bar is not None, "we passed use_timing_bar=True"
        self.timing_bar.highlightedUser = bare_user

    def _on_rba_login(self, token: pyrbac.Token) -> None:
        self._control_pane.rbac_login(token)

    def _on_rba_logout(self) -> None:
        self._control_pane.rbac_logout()
