from cernml import coi
from PyQt5.QtWidgets import (
    QWidget,
    QPushButton,
    QScrollArea,
    QGridLayout,
    QHBoxLayout,
)
from PyQt5.QtGui import *
from PyQt5.QtCore import QThreadPool

from .param_widget import ParamsForm
from .config_widget import ConfigureDialog
from ..utils.utilities import IncaAccelerators
from ..algos.single_opt import (
    OptimizerRunner,
    all_single_algos_dict,
)


class DecoratedControlPane(object):
    def __init__(self, mainwindow):
        self.mainwindow = mainwindow
        self.selected_env = None
        self.selected_algo = None
        self.allEnvs = None
        self.controlPane = self.mainwindow.controlPane
        self.algoConfigPane = QScrollArea()
        mainwindow.plotTabWidget.addTab(self.algoConfigPane, "Algo config")
        self.mainwindow.configEnvButton.clicked.connect(self.on_config_env)
        self.mainwindow.configEnvButton.setEnabled(False)

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
        self.selected_algo_name = self.mainwindow.algoCombo.currentText()
        self.threadpool = QThreadPool()
        self.opt_runner = OptimizerRunner(None)
        # Lambda instead of direct binding because `self.plotPane` only is set
        # at a later point.
        self.opt_runner.signals.objective_updated.connect(
            lambda x, y: self.plotPane.curve.setData(x, y)
        )
        self.opt_runner.signals.actors_updated.connect(
            lambda x, y: self.plotPane.setActorsCurveData(x, y)
        )
        self.opt_runner.signals.optimisation_finished.connect(lambda: self.finish())
        self.mainwindow.algoCombo.currentTextChanged.connect(lambda x: self.set_algo(x))
        self.mainwindow.environmentCombo.currentTextChanged.connect(
            self.on_env_selected
        )

        self.mainwindow.launchButton.clicked.connect(self.launch_opt)
        self.mainwindow.stopButton.clicked.connect(self.stop_opt)
        self.mainwindow.resetButton.clicked.connect(self.reset_opt)
        self.mainwindow.stopButton.setEnabled(False)

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
        self.mainwindow.resetButton.setEnabled(False)
        self.mainwindow.stopButton.setEnabled(True)
        self.opt_runner = OptimizerRunner(self.selected_algo)
        self.threadpool.start(self.opt_runner)

    def reset_opt(self):
        if self.selected_env is None:
            return
        if self.selected_algo is None:
            return
        self.selected_env.compute_single_objective(self.selected_algo.x_0)

    def stop_opt(self):
        self.mainwindow.stopButton.setEnabled(False)
        self.opt_runner.cancel()

    def on_env_selected(self, env_name):
        if env_name:
            self.selected_env = self.allEnvs.getSelectedEnv(env_name, self.japc)
            algo_class = all_single_algos_dict[self.selected_algo_name]
            self.selected_algo = algo_class(self.selected_env)
            (dimension,) = self.selected_env.optimization_space.shape
            self.plotPane.setActorCount(dimension)
            self.mainwindow.configEnvButton.setEnabled(
                isinstance(self.selected_env.unwrapped, coi.Configurable)
            )
        else:
            self.selected_env = None
            self.selected_algo = None
            self.mainwindow.configEnvButton.setEnabled(False)
        self.update_algo_params_gui()

    def finish(self):
        self.mainwindow.launchButton.setEnabled(True)
        self.mainwindow.resetButton.setEnabled(True)
        self.mainwindow.stopButton.setEnabled(False)

    def set_algo(self, algo_name):
        if self.selected_env is None:
            return
        self.selected_algo_name = algo_name
        if algo_name:
            algo_class = all_single_algos_dict[self.selected_algo_name]
            self.selected_algo = algo_class(self.selected_env)
        else:
            self.selected_algo = None
        self.update_algo_params_gui()

    def update_algo_params_gui(self):
        if self.selected_algo is None:
            self.algoConfigPane.setWidget(None)
            return
        params = self.selected_algo.opt_params
        params_widget = ParamsForm(params)
        self.algoConfigPane.setWidget(params_widget)

    def on_config_env(self):
        dialog = ConfigureDialog(self.selected_env, self.mainwindow.centralwidget)
        name = type(self.selected_env.unwrapped).__name__
        dialog.setWindowTitle(f"Configure {name} ...")
        dialog.open()
