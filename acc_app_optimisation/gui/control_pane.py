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

from .config_widget import ConfigureDialog
from .figures_view import FiguresView
from .. import envs as environments
from ..algos.single_opt import (
    OptimizerRunner,
    all_single_algos_dict,
)


class DecoratedControlPane(object):
    def __init__(self, mainwindow, plotpane):
        self.mainwindow = mainwindow
        self.plotpane = plotpane
        self.selected_env = None
        self.selected_algo = None
        self._japc = None
        self.controlPane = self.mainwindow.controlPane
        self.mainwindow.configEnvButton.clicked.connect(self.on_config_env)
        self.mainwindow.configOptButton.clicked.connect(self.on_config_opt)

        self.mainwindow.machinePaneLabel.setFont(QFont("Arial", 12, QFont.Bold))
        self.mainwindow.environmentLabel.setFont(QFont("Arial", 12, QFont.Bold))
        self.mainwindow.algoSelectionLabel.setFont(QFont("Arial", 12, QFont.Bold))

        self.envRenderPane = FiguresView()
        mainwindow.plotTabWidget.addTab(self.envRenderPane, "Render output")

        self.mainwindow.setting_tab_widget.setTabText(0, "CONFIG")
        self.mainwindow.setting_tab_widget.removeTab(1)

        for algo in all_single_algos_dict:
            self.mainwindow.algoCombo.addItem(algo)
        self.selected_algo_name = self.mainwindow.algoCombo.currentText()
        self.threadpool = QThreadPool()
        self.opt_runner = OptimizerRunner(None)
        self.opt_runner.signals.objective_updated.connect(
            self.plotpane.objective_curve.setData
        )
        self.opt_runner.signals.actors_updated.connect(self.plotpane.setActorsCurveData)
        self.opt_runner.signals.constraints_updated.connect(
            self.plotpane.setConstraintsCurveData
        )
        self.opt_runner.signals.optimisation_finished.connect(self.finish)
        self.mainwindow.algoCombo.currentTextChanged.connect(self.set_algo)
        self.mainwindow.environmentCombo.currentTextChanged.connect(
            self.on_env_selected
        )

        self.mainwindow.launchButton.clicked.connect(self.launch_opt)
        self.mainwindow.stopButton.clicked.connect(self.stop_opt)
        self.mainwindow.resetButton.clicked.connect(self.reset_opt)

    def updateMachine(self, machine: coi.Machine) -> None:
        combo_box = self.mainwindow.environmentCombo
        combo_box.clear()
        combo_box.addItems(environments.get_env_names_by_machine(machine))

    def japc(self):
        return self._japc

    def setJapc(self, japc):
        self._japc = japc

    def launch_opt(self):
        self.mainwindow.launchButton.setEnabled(False)
        self.mainwindow.resetButton.setEnabled(False)
        self.mainwindow.stopButton.setEnabled(True)
        self._add_render_output()
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
            self.selected_env = environments.make_env_by_name(env_name, self._japc)
            algo_class = all_single_algos_dict[self.selected_algo_name]
            self.selected_algo = algo_class(self.selected_env)
            (dimension,) = self.selected_env.optimization_space.shape
            self.plotpane.setActorCount(dimension)
            self.plotpane.clearConstraintCurves()
            self.mainwindow.configEnvButton.setEnabled(
                isinstance(self.selected_env.unwrapped, coi.Configurable)
            )
            self.mainwindow.configOptButton.setEnabled(True)
        else:
            self.selected_env = None
            self.selected_algo = None
            self.mainwindow.configEnvButton.setEnabled(False)
            self.mainwindow.configOptButton.setEnabled(False)

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
            self.mainwindow.configOptButton.setEnabled(True)
        else:
            self.selected_algo = None
            self.mainwindow.configOptButton.setEnabled(False)

    def on_config_env(self):
        dialog = ConfigureDialog(self.selected_env, self.mainwindow.centralwidget)
        name = type(self.selected_env.unwrapped).__name__
        dialog.setWindowTitle(f"Configure {name} ...")
        dialog.open()

    def _add_render_output(self):
        env = self.selected_env
        if "matplotlib_figures" in env.metadata.get("render.modes", []):
            figures = env.render(mode="matplotlib_figures")
            self.envRenderPane.setFigures(figures)
        else:
            self.envRenderPane.clear()

    def on_config_opt(self):
        dialog = ConfigureDialog(self.selected_algo, self.mainwindow.centralwidget)
        name = type(self.selected_algo).__name__
        dialog.setWindowTitle(f"Configure {name} ...")
        dialog.open()
