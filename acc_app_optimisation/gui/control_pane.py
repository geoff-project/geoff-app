#!/usr/bin/env python

"""Module containing the main GUI logic of the app."""

import typing as t
from logging import getLogger

# Warning: jpype.imports must be imported before pjlsa! Otherwise,
# JPype's import hooks don't get set up correctly and qt_lsa_selector
# cannot import the CERN packages.
import jpype.imports  # pylint: disable=unused-import

import numpy as np
from PyQt5 import QtCore, QtWidgets
from cernml import coi
from pjlsa import pjlsa
from pyjapc import PyJapc

from ._control_pane_generated import Ui_ControlPane
from .config_widget import ConfigureDialog
from .plot_manager import PlotManager
from .. import envs
from ..algos import single_opt
from ..qt_lsa_selector import LsaSelectorWidget
from ..utils.accelerators import IncaAccelerators

LOG = getLogger(__name__)


class CycleSettings:
    """The current settings necessary to create a PyJapc object."""

    # TODO: Turn into dataclass once Python 3.7 is required.
    # pylint: disable = too-few-public-methods
    def __init__(
        self, *, accelerator: IncaAccelerators, context: str, user: str
    ) -> None:
        self.accelerator = accelerator
        self.context = context
        self.user = user


class ControlPane(QtWidgets.QWidget, Ui_ControlPane):
    """The sidebar of the app."""

    def __init__(
        self, parent: t.Optional[QtWidgets.QWidget] = None, *, plot_manager: PlotManager
    ) -> None:
        super().__init__(parent)
        self.setupUi(self)
        self.accelerator = IncaAccelerators.SPS
        self.selected_algo = None
        self.selected_env = None
        self.plot_manager = plot_manager

        # Create a dummy runner and connect its (class-scope) signals to
        # handlers. Use QueuedConnection as the signals cross thread
        # boundaries.
        self._opt_last_starting_point: t.Optional[np.ndarray] = None
        self.opt_runner = single_opt.OptimizerRunner(None)
        self.opt_runner.signals.objective_updated.connect(
            self.plot_manager.set_objective_curve_data, QtCore.Qt.QueuedConnection
        )
        self.opt_runner.signals.actors_updated.connect(
            self.plot_manager.set_actors_curve_data, QtCore.Qt.QueuedConnection
        )
        self.opt_runner.signals.constraints_updated.connect(
            self.plot_manager.set_constraints_curve_data, QtCore.Qt.QueuedConnection
        )
        self.opt_runner.signals.optimisation_finished.connect(
            self._on_finished, QtCore.Qt.QueuedConnection
        )

        self.launchButton.clicked.connect(self._on_launch_clicked)
        self.stopButton.clicked.connect(self._on_stop_clicked)
        self.resetButton.clicked.connect(self._on_reset_clicked)

        self.environmentCombo.currentTextChanged.connect(self._on_env_changed)
        self.configEnvButton.clicked.connect(self._on_config_env)
        self.configOptButton.clicked.connect(self._on_config_algo)
        self.showConstraintsCheckbox.toggled.connect(
            self.plot_manager.set_constraints_plot_visible
        )

        self.algoCombo.currentTextChanged.connect(
            lambda name: self._on_algo_changed(single_opt.ALL_ALGOS[name])
        )
        self.algoCombo.addItems(single_opt.ALL_ALGOS)

        lsa_dummy = self.lsaSelectorWidget
        self.lsaSelectorWidget = LsaSelectorWidget(
            pjlsa.LSAClient("gpn"),
            accelerator=self.accelerator.lsa_name,
            parent=self,
            as_dock=False,
        )
        self.layout().replaceWidget(lsa_dummy, self.lsaSelectorWidget)
        self.lsaSelectorWidget.selectionChanged.connect(self._on_lsa_cycle_changed)

        self.machineCombo.currentTextChanged.connect(
            lambda name: self._on_accelerator_changed(IncaAccelerators[name])
        )
        self.machineCombo.addItems(acc.name for acc in IncaAccelerators)

    def algoClass(self) -> t.Optional[t.Type[single_opt.BaseOptimizer]]:
        """The currently selected algorithm class."""
        # pylint: disable = invalid-name
        name = self.algoCombo.currentText()
        return single_opt.ALL_ALGOS.get(name, None)

    def cycleSettings(self) -> CycleSettings:
        """Return the current accelerator/cycle settings."""
        # pylint: disable = invalid-name
        return CycleSettings(
            accelerator=self.accelerator,
            context=self.lsaSelectorWidget.getContext(),
            user=self.lsaSelectorWidget.getUser(),
        )

    def _make_japc(self) -> PyJapc:
        """Create a fresh and up-to-date JAPC object."""
        selector = self.lsaSelectorWidget.getUser()
        return PyJapc(selector, noSet=False, incaAcceleratorName="AD")

    def _on_accelerator_changed(self, accelerator: IncaAccelerators) -> None:
        """Handler for the accelerator selection."""
        LOG.debug("accelerator changed: %s", accelerator)
        self.accelerator = accelerator
        self.lsaSelectorWidget.setAccelerator(accelerator.lsa_name)
        self.environmentCombo.clear()
        self.environmentCombo.addItems(
            envs.get_env_names_by_machine(accelerator.machine)
        )

    def _on_lsa_cycle_changed(self, _cycle_name: str) -> None:
        """Handler for the LSA cycle selection."""
        settings = self.cycleSettings()
        LOG.debug("cycle changed: %s, %s", settings.context, settings.user)
        # TODO: We have to recreate the environment because the JAPC
        # object has changed.

    def _on_env_changed(self, env_name: str) -> None:
        """Handler for the environment selection."""
        LOG.debug("environment changed: %s", env_name)
        self._opt_last_starting_point = None
        self.resetButton.setEnabled(False)
        if not env_name:
            self.selected_env = None
            LOG.debug("new environment: %s", self.selected_env)
            self.configEnvButton.setEnabled(False)
            self.showConstraintsCheckbox.setEnabled(False)
            self._on_algo_changed(None)
            return

        japc = self._make_japc()
        self.selected_env = envs.make_env_by_name(env_name, japc)
        LOG.debug("new environment: %s", self.selected_env)

        constraints = self.selected_env.constraints
        self.showConstraintsCheckbox.setEnabled(bool(constraints))
        LOG.debug("number of constraints: %d", len(constraints))

        is_configurable = isinstance(self.selected_env.unwrapped, coi.Configurable)
        self.configEnvButton.setEnabled(is_configurable)
        LOG.debug("configurable: %s", is_configurable)

        self._on_algo_changed(self.algoClass())

    def _on_algo_changed(
        self, algo_class: t.Optional[t.Type[single_opt.BaseOptimizer]]
    ) -> None:
        """Handler for the algorithm selection."""
        LOG.debug("algorithm changed: %s with env %s", algo_class, self.selected_env)
        if self.selected_env and algo_class:
            self.selected_algo = algo_class(self.selected_env)
        else:
            self.selected_algo = None
        LOG.debug("new algorithm: %s", self.selected_algo)
        self.configOptButton.setEnabled(
            isinstance(self.selected_algo, coi.Configurable)
        )

    def _on_config_env(self) -> None:
        """Handler for the env configuration."""
        env = self.selected_env
        if not isinstance(env.unwrapped, coi.Configurable):
            LOG.error("not configurable: %s", env.unwrapped)
            return
        dialog = ConfigureDialog(env, self.window())
        name = type(env.unwrapped).__name__
        dialog.setWindowTitle(f"Configure {name} ...")
        dialog.open()

    def _on_config_algo(self) -> None:
        """Handler for the algorith, configuration."""
        if not isinstance(self.selected_algo, coi.Configurable):
            LOG.error("not configurable: %s", self.selected_algo)
            return
        dialog = ConfigureDialog(self.selected_algo, self.window())
        name = type(self.selected_algo).__name__
        dialog.setWindowTitle(f"Configure {name} ...")
        dialog.open()

    def _on_launch_clicked(self) -> None:
        """Handler for the Launch button."""
        if not self.selected_algo:
            LOG.error("cannot launch, no algorithm")
            return
        LOG.debug("launching ...")
        self.launchButton.setEnabled(False)
        self.resetButton.setEnabled(False)
        self.stopButton.setEnabled(True)
        self._add_render_output()
        self.opt_runner = single_opt.OptimizerRunner(self.selected_algo)
        self._opt_last_starting_point = self.opt_runner.x_0.copy()
        threadpool = QtCore.QThreadPool.globalInstance()
        threadpool.start(self.opt_runner)

    def _on_stop_clicked(self) -> None:
        """Handler for the Stop button."""
        LOG.debug("stopping ...")
        self.stopButton.setEnabled(False)
        self.opt_runner.cancel()

    def _on_reset_clicked(self) -> None:
        """Handler for the Reset button."""
        x_0 = self._opt_last_starting_point
        if self.selected_env is None or x_0 is None:
            LOG.error("cannot reset: env=%s, x_0=%s", self.selected_env, x_0)
            return
        LOG.debug("resetting to %s ...", x_0)
        self.selected_env.compute_single_objective(x_0)

    def _on_finished(self) -> None:
        """Handler for when optimization is finished."""
        LOG.debug("optimization finished")
        self.launchButton.setEnabled(True)
        self.resetButton.setEnabled(True)
        self.stopButton.setEnabled(False)

    def _add_render_output(self) -> None:
        env = self.selected_env
        render_modes = env.metadata.get("render.modes", [])
        if "matplotlib_figures" in render_modes:
            figures = env.render(mode="matplotlib_figures")
            self.plot_manager.replace_mpl_figures(figures)
        else:
            self.plot_manager.clear_mpl_figures()
