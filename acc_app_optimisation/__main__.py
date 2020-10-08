from PyQt5.QtWidgets import *
import sys
import pyjapc
from pjlsa import pjlsa


from acc_app_optimisation.gui.generated_main_window import Ui_MainWindow
from qt_lsa_selector.widget.lsa_view import LsaSelectorWidget
from acc_app_optimisation.utils.utilities import IncaAccelerators
import acc_app_optimisation.gui.control_pane  as gui_control_core
import acc_app_optimisation.gui.plot_pane as plotting



class CentralWindow(QMainWindow):

    def __init__(self,*args,**kargs):
        super(QMainWindow,self).__init__(*args,**kargs)

        self.mainwindow = Ui_MainWindow()
        self.mainwindow.setupUi(self)

        self.accelerator = IncaAccelerators.SPS

        self.japc = pyjapc.PyJapc('', noSet=False, incaAcceleratorName=self.accelerator.acc_name)

        decoratedControlPane = gui_control_core.DecoratedControlPane(self.mainwindow)

        self.plotPane = plotting.PlotPane(self.mainwindow)
        decoratedControlPane.setPlotPane(self.plotPane)

        self.lsa = pjlsa.LSAClient('gpn')
        self.lsaSelectorWidget = LsaSelectorWidget(self, self.lsa, self.japc, accelerator='sps', as_dock=False)
        self.mainwindow.controlPane.layout().addWidget(self.lsaSelectorWidget)


        self.lsaSelectorWidget.selectionChanged.connect(
            lambda x: self.set_selector(self.lsaSelectorWidget.getUser())
        )

        self.mainwindow.machineCombo.currentTextChanged.connect(lambda x: self.set_accelerator(x))




    def set_selector(self, selector):
        pass

    def set_accelerator(self,acceleratorname):
        self.mainwindow.controlPane.layout().removeWidget(self.lsaSelectorWidget)
        self.lsaSelectorWidget= LsaSelectorWidget(self, self.lsa, self.japc, accelerator=acceleratorname, as_dock=False)
        self.mainwindow.controlPane.layout().addWidget(self.lsaSelectorWidget)




if __name__== '__main__':
    app = QApplication(sys.argv)

    window = CentralWindow()
    window.show()


    sys.exit(app.exec_())