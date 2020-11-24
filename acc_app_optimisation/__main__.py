import logging
import sys

# Warning: jpype.imports must be imported before pjlsa! Otherwise, JPype's
# import hooks don't get set up correctly and qt_lsa_selector cannot import the
# CERN packages.
import jpype.imports  # pylint: disable=unused-import

import pyjapc
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import *
from pjlsa import pjlsa

from acc_app_optimisation.gui import plot_pane as plotting
from acc_app_optimisation.gui.control_pane import DecoratedControlPane
from acc_app_optimisation.gui.generated_main_window import Ui_MainWindow
from acc_app_optimisation.qt_lsa_selector import LsaSelectorWidget
from acc_app_optimisation.utils.accelerators import IncaAccelerators


class CentralWindow(QMainWindow):
    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)

        self.mainwindow = Ui_MainWindow()
        self.mainwindow.setupUi(self)

        self.lsaSelectorWidget = LsaSelectorWidget(
            self,
            lsa=pjlsa.LSAClient("gpn"),
            japc=pyjapc.PyJapc("", noSet=False, incaAcceleratorName="AD"),
            accelerator="sps",
            as_dock=False,
        )
        lsa_layout = QGridLayout()
        lsa_layout.setSpacing(0)
        lsa_layout.addWidget(self.lsaSelectorWidget)
        self.mainwindow.controlPane.setLayout(lsa_layout)
        self.mainwindow.controlPane.setStyleSheet("border: 1px solid black;")

        self.accelerator = IncaAccelerators.SPS
        self.plotpane = plotting.PlotPane(self.mainwindow)
        self.decoratedControlPane = DecoratedControlPane(self.mainwindow, self.plotpane)
        self.decoratedControlPane.updateMachine(self.accelerator.machine)
        # This passes the JAPC object onto decoratedControlPane.
        self.on_lsa_cycle_changed()

        self.lsaSelectorWidget.selectionChanged.connect(self.on_lsa_cycle_changed)

        self.mainwindow.machineCombo.setFont(QFont("Arial", 13))
        self.mainwindow.machineCombo.addItems(acc.name for acc in IncaAccelerators)
        self.mainwindow.machineCombo.currentTextChanged.connect(
            self.on_accelerator_changed
        )

    def on_lsa_cycle_changed(self):
        # TODO: We need to recreate the Japc object on every environment
        # change.
        japc = self.lsaSelectorWidget.getPyJapcObject()
        self.decoratedControlPane.setJapc(japc)

    def on_accelerator_changed(self, acc_name: str) -> None:
        self.accelerator = IncaAccelerators[acc_name]
        self.decoratedControlPane.updateMachine(self.accelerator.machine)
        self.lsaSelectorWidget.setAccelerator(self.accelerator.lsa_name)


def main(argv):
    """Main function. Pass sys.argv."""
    logging.basicConfig(level=logging.INFO)
    app = QApplication(sys.argv)
    window = CentralWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
