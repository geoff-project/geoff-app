import sys

# Warning: jpype.imports must be imported before pjlsa! Otherwise, JPype's
# import hooks don't get set up correctly and qt_lsa_selector cannot import the
# CERN packages.
import jpype.imports  # pylint: disable=unused-import

import pyjapc
from PyQt5.QtWidgets import *
from pjlsa import pjlsa
from qt_lsa_selector.widget.lsa_view import LsaSelectorWidget

from acc_app_optimisation.gui.generated_main_window import Ui_MainWindow
from acc_app_optimisation.utils.utilities import IncaAccelerators
from acc_app_optimisation.utils import utilities
from acc_app_optimisation.gui.control_pane import DecoratedControlPane
from acc_app_optimisation.gui import plot_pane as plotting
from acc_app_optimisation.envs.envs_prep import AllEnvs


class CentralWindow(QMainWindow):
    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)

        self.mainwindow = Ui_MainWindow()
        self.mainwindow.setupUi(self)

        self.accelerator = IncaAccelerators.SPS

        self.japc = pyjapc.PyJapc("", noSet=False, incaAcceleratorName="AD")

        self.decoratedControlPane = DecoratedControlPane(self.mainwindow)
        self.decoratedControlPane.set_japc(self.japc)

        self.plotPane = plotting.PlotPane(self.mainwindow)
        self.decoratedControlPane.setPlotPane(self.plotPane)

        self.allEnvs = AllEnvs()
        self.allEnvs.setAccelerator(self.accelerator)
        self.decoratedControlPane.setAllEnvs(self.allEnvs)

        self.lsa = pjlsa.LSAClient("gpn")
        self.lsaSelectorWidget = LsaSelectorWidget(
            self, self.lsa, self.japc, accelerator="sps", as_dock=False
        )
        lsa_layout = QGridLayout()
        lsa_layout.setSpacing(0)
        lsa_layout.addWidget(self.lsaSelectorWidget)
        self.mainwindow.controlPane.setLayout(lsa_layout)
        self.mainwindow.controlPane.setStyleSheet("border: 1px solid black;")

        self.lsaSelectorWidget.selectionChanged.connect(self.on_lsa_cycle_changed)
        self.mainwindow.machineCombo.currentTextChanged.connect(
            self.on_accelerator_changed
        )

    def on_lsa_cycle_changed(self):
        user = self.lsaSelectorWidget.getUser()
        self.japc.setSelector(user)

    def on_accelerator_changed(self, acc_name):
        if acc_name == "linac3":
            lsa_acc_name = "leir"
        elif acc_name == "linac4":
            lsa_acc_name = "psb"
        else:
            lsa_acc_name = acc_name
        self.accelerator = utilities.getAcceleratorFromAcceleratorName(acc_name)
        self.allEnvs.setAccelerator(self.accelerator)
        self.decoratedControlPane.setAllEnvs(self.allEnvs)
        self.lsaSelectorWidget.setAccelerator(lsa_acc_name)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = CentralWindow()
    window.show()

    sys.exit(app.exec_())
