from PyQt5.QtWidgets import *
import sys
import pyjapc
from pjlsa import pjlsa


from acc_app_optimisation.gui.generated_main_window import Ui_MainWindow
from qt_lsa_selector.widget.lsa_view import LsaSelectorWidget
from acc_app_optimisation.utils.utilities import IncaAccelerators
import acc_app_optimisation.utils.utilities as utilities
from acc_app_optimisation.gui.control_pane import DecoratedControlPane
import acc_app_optimisation.gui.plot_pane as plotting
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
        self.mainwindow.controlPane.layout().addWidget(self.lsaSelectorWidget)

        self.lsaSelectorWidget.selectionChanged.connect(
            lambda x: self.set_selector(self.lsaSelectorWidget.getUser())
        )

        self.mainwindow.machineCombo.currentTextChanged.connect(self.set_accelerator)

    def set_selector(self, selector):
        self.japc.setSelector(selector)

    def set_accelerator(self, acceleratorname):
        self.accelerator = utilities.getAcceleratorFromAcceleratorName(acceleratorname)
        self.allEnvs.setAccelerator(self.accelerator)
        self.decoratedControlPane.setAllEnvs(self.allEnvs)
        self.mainwindow.controlPane.layout().removeWidget(self.lsaSelectorWidget)
        self.japc = pyjapc.PyJapc("", noSet=False, incaAcceleratorName="AD")
        self.decoratedControlPane.set_japc(self.japc)
        try:
            self.lsaSelectorWidget = LsaSelectorWidget(
                self, self.lsa, self.japc, accelerator=acceleratorname, as_dock=False
            )
        except KeyError as exc:
            (accelerator,) = exc.args
            if accelerator in ("awake", "leir"):
                self.lsaSelectorWidget = QLabel("AWAKE/LEIR cycles are not implemented")
            else:
                raise
        self.mainwindow.controlPane.layout().addWidget(self.lsaSelectorWidget)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = CentralWindow()
    window.show()

    sys.exit(app.exec_())
