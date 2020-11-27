#!/usr/bin/env python
"""Main entry point of this package."""

import argparse
import logging
import sys
import typing as t

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt

from acc_app_optimisation import gui as app_gui
from acc_app_optimisation import foreign_imports


LOG = logging.getLogger(__name__)


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


class MainWindow(QtWidgets.QMainWindow):
    """The main window."""

    def __init__(self) -> None:
        super().__init__()
        self._mdi = app_gui.PopoutMdiArea(viewMode=QtWidgets.QMdiArea.TabbedView)
        self.setCentralWidget(self._mdi)
        self._plot_manager = app_gui.PlotManager(self._mdi)
        self.runner = None

        self._control_pane = app_gui.ControlPane(plot_manager=self._plot_manager)
        dock = DumbDockWidget()
        dock.setWidget(self._control_pane)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

        # We must keep ownership of this QMenu to keep the GC from
        # reclaiming it.
        self._view_menu = MdiViewMenu("&View", self._mdi)
        menubar = QtWidgets.QMenuBar(self)
        menubar.addMenu(self._view_menu)
        self.setMenuBar(menubar)

        self.setStatusBar(QtWidgets.QStatusBar(self))


def get_parser() -> argparse.ArgumentParser:
    """Return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="GeOFF: Generic Optimization Framework and Frontend"
    )
    parser.add_argument(
        "foreign_imports",
        nargs="*",
        type=str,
        help="Path to additional modules and packages that shall be "
        "imported; child modules may be imported by appending them, "
        "delimited by `::`",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_const",
        const=logging.WARNING,
        default=logging.INFO,
        dest="verbosity",
        help="Only show warnings and errors",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_const",
        const=logging.DEBUG,
        dest="verbosity",
        help="Show debug-level information",
    )
    return parser


def main(argv):
    """Main function. Pass sys.argv."""
    args = get_parser().parse_args(argv[1:])
    logging.basicConfig(level=args.verbosity)
    for path in args.foreign_imports:
        foreign_imports.import_from_path(path)
    app = QtWidgets.QApplication(argv)
    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
