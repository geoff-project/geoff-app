from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from acc_app_optimisation.utils.utilities import IncaAccelerators
from PyQt5.QtCore import QThreadPool

from acc_app_optimisation.algos.single_opt import (
    OptimizerRunner,
    all_single_algos_dict,
)


class DecoratedControlPane(object):
    def __init__(self, mainwindow):
        self.mainwindow = mainwindow
        self.allEnvs = None
        self.controlPane = self.mainwindow.controlPane
        algoConfigPane = QWidget()
        mainwindow.plotTabWidget.addTab(algoConfigPane, "Algo config")

        self.mainwindow.machinePaneLabel.setFont(QFont("Arial", 12, QFont.Bold))
        self.mainwindow.environmentLabel.setFont(QFont("Arial", 12, QFont.Bold))
        self.mainwindow.algoSelectionLabel.setFont(QFont("Arial", 12, QFont.Bold))

        self.mainwindow.setting_tab_widget.setTabText(0, "CONFIG")
        self.mainwindow.setting_tab_widget.removeTab(1)

        self.machineCombo = self.mainwindow.machineCombo
        font = QFont("Arial", 13)
        self.machineCombo.setFont(font)

        for val in IncaAccelerators:
            self.machineCombo.addItem(val.lsa_name)

        layout = QGridLayout()
        self.controlPane.setLayout(layout)
        self.controlPane.setStyleSheet("border: 1px solid black;")

        self.controlPane.layout().setSpacing(0)

        for algo in all_single_algos_dict:
            self.mainwindow.algoCombo.addItem(algo)

        self.threadpool = QThreadPool()
        self.algo_selected = self.mainwindow.algoCombo.currentText()
        self.opt_runner = OptimizerRunner()
        self.opt_runner.signals.objetive_updated.connect(
            lambda x, y: self.plotPane.curve.setData(x, y)
        )
        self.opt_runner.signals.optimisation_finished.connect(lambda: self.finish())
        self.mainwindow.algoCombo.highlighted.connect(lambda x: self.set_algo(x))
        self.mainwindow.algoCombo.currentTextChanged.connect(lambda x: self.set_algo(x))

        self.mainwindow.launchButton.clicked.connect(lambda: self.launch_opt())
        self.mainwindow.stopButton.clicked.connect(lambda: self.stop_opt())
        self.mainwindow.resetButton.clicked.connect(lambda: self.reset_opt())

    def setPlotPane(self, plotPane):
        self.plotPane = plotPane

    def setAllEnvs(self, allEnvs):
        self.allEnvs = allEnvs
        self.mainwindow.environmentCombo.clear()
        for env in self.allEnvs.getAllEnvsForAccelerator():
            self.mainwindow.environmentCombo.addItem(env)

    def set_japc(self, japc):
        self.japc = japc

    def launch_opt(self):
        self.mainwindow.launchButton.setEnabled(False)
        env = self.allEnvs.getSelectedEnv(
            self.mainwindow.environmentCombo.currentText(), self.japc
        )
        algo = all_single_algos_dict[self.algo_selected](env)
        self.opt_runner = OptimizerRunner()
        self.opt_runner.setOptimizer(algo)
        self.threadpool.start(self.opt_runner)

    def reset_opt(self):
        pass

    def stop_opt(self):
        pass

    def finish(self):
        self.mainwindow.launchButton.setEnabled(True)

    def set_algo(self, algo_name):
        if isinstance(algo_name, str):
            self.algo_selected = algo_name
        else:
            self.algo_selected = self.mainwindow.algoCombo.currentText()
