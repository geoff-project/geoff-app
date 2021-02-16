#!/usr/bin/env python

"""Module containing the main GUI logic of the app."""

import traceback
import typing as t
from collections import defaultdict
from logging import getLogger

# Warning: jpype.imports must be imported before pjlsa! Otherwise,
# JPype's import hooks don't get set up correctly and qt_lsa_selector
# cannot import the CERN packages.
import jpype.imports  # pylint: disable=unused-import
from accwidgets.lsa_selector import (
    AbstractLsaSelectorResidentContext,
    LsaSelector,
    LsaSelectorAccelerator,
    LsaSelectorModel,
)
from cernml import coi, coi_funcs
from pjlsa import pjlsa
from pyjapc import PyJapc
from PyQt5 import QtCore, QtWidgets

from .. import envs
from ..algos import single_opt
from ._control_pane_generated import Ui_ControlPane
from .cfgdialog import ProblemConfigureDialog, PureConfigureDialog
from .plot_manager import PlotManager

LOG = getLogger(__name__)


class CreatingEnvDialog(QtWidgets.QDialog):
    """A button-less dialog that tells the user to wait."""

    def __init__(self, parent: t.Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(
            QtWidgets.QLabel("Environment is being initialized, please wait ...")
        )


def translate_machine(machine: coi.Machine) -> t.Optional[LsaSelectorAccelerator]:
    """Fetch the LSA accelerator for a given CERN machine."""
    return {
        coi.Machine.NoMachine: None,
        coi.Machine.Linac2: None,
        coi.Machine.Linac3: LsaSelectorAccelerator.LEIR,
        coi.Machine.Linac4: LsaSelectorAccelerator.PSB,
        coi.Machine.Leir: LsaSelectorAccelerator.LEIR,
        coi.Machine.PS: LsaSelectorAccelerator.PS,
        coi.Machine.PSB: LsaSelectorAccelerator.PSB,
        coi.Machine.SPS: LsaSelectorAccelerator.SPS,
        coi.Machine.Awake: LsaSelectorAccelerator.AWAKE,
        coi.Machine.LHC: LsaSelectorAccelerator.LHC,
    }.get(machine)


class ControlPane(QtWidgets.QWidget, Ui_ControlPane):
    """The sidebar of the app."""

    def __init__(
        self,
        parent: t.Optional[QtWidgets.QWidget] = None,
        *,
        plot_manager: PlotManager,
        lsa: pjlsa.LSAClient,
    ) -> None:
        super().__init__(parent)
        self.setupUi(self)
        self.accelerator = coi.Machine.SPS
        self.plot_manager = plot_manager
        self.last_lsa_selection: t.DefaultDict[coi.Machine, str] = defaultdict(str)

        # Create a dummy runner and connect its (class-scope) signals to
        # handlers. Use QueuedConnection as the signals cross thread
        # boundaries.
        self.opt_runner = single_opt.OptimizerRunner()
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

        lsa_dummy = self.lsaSelector
        self.lsaSelector = LsaSelector(
            model=LsaSelectorModel(LsaSelectorAccelerator.SPS, lsa, resident_only=True),
            parent=self,
        )
        self.layout().replaceWidget(lsa_dummy, self.lsaSelector)
        self.lsaSelector.userSelectionChanged.connect(self._on_lsa_user_changed)
        self.lsaSelector.select_user("")

        # Only allow those machines for which there is an LSA
        # accelerator available.
        self.machineCombo.addItems(
            machine.name for machine in coi.Machine if translate_machine(machine)
        )
        self.machineCombo.currentTextChanged.connect(
            lambda name: self._on_accelerator_changed(coi.Machine[name])
        )
        self.machineCombo.setCurrentText(self.accelerator.name)

    def algoClass(self) -> t.Optional[t.Type[single_opt.BaseOptimizer]]:
        """The currently selected algorithm class."""
        # pylint: disable = invalid-name
        name = self.algoCombo.currentText()
        return single_opt.ALL_ALGOS.get(name, None)

    def _update_env(self, env: t.Optional[coi.Problem]) -> None:
        """Update the selected env _object_ and the GUI.

        This is internally called by various event handlers whenever a
        new environment is available. It updates the GUI's buttons as
        needed.

        This must only be called when the environment has actually
        changed or is to be removed. Do not call it twice with the same
        non-None env.
        """
        assert env is None or env is not self.opt_runner.problem, env
        self.opt_runner.set_problem(env)
        self.resetButton.setEnabled(False)
        self.configOptButton.setEnabled(
            isinstance(self.opt_runner.optimizer, coi.Configurable)
        )
        if env is None:
            self.configEnvButton.setEnabled(False)
            self.showConstraintsCheckbox.setEnabled(False)
        else:
            constraints = getattr(env, "constraints", ())
            self.showConstraintsCheckbox.setEnabled(bool(constraints))
            LOG.debug("number of constraints: %d", len(constraints))
            is_configurable = _is_env_configurable(env)
            self.configEnvButton.setEnabled(is_configurable)
            LOG.debug("configurable: %s", is_configurable)

    def _make_japc(self) -> PyJapc:
        """Create a fresh and up-to-date JAPC object."""
        context = self.lsaSelector.selected_context
        if context is None:
            raise ValueError("JAPC required but no context has been selected")
        assert isinstance(context, AbstractLsaSelectorResidentContext), context
        user_name = t.cast(AbstractLsaSelectorResidentContext, context).user
        # No particular reason to pick "AD" as the INCA server. We use
        # it because it is frequented by other applications less often,
        # so it might reply quicker. Whether this is true is untested.
        japc = PyJapc(user_name, noSet=False, incaAcceleratorName="AD")
        LOG.debug("new JPAC instance, selector: %s", japc.getSelector())
        return japc

    def _on_accelerator_changed(self, machine: coi.Machine) -> None:
        """Handler for the accelerator selection."""
        LOG.debug("accelerator changed: %s", machine)
        # Remove all environments before doing anything else, to prevent
        # spurious updates.
        self.environmentCombo.clear()
        self.accelerator = machine
        self.lsaSelector.accelerator = translate_machine(machine)
        # Re-select the last context for this accelerator. This makes
        # use of `defaultdict`'s behavior and selects the unmultiplexed
        # context (`user_name == ""`) if none has been selected before.
        self.lsaSelector.select_user(self.last_lsa_selection[self.accelerator])
        # Add environments last. Only _now_, `_on_env_changed()` is
        # allowed to do non-trivial work.
        self.environmentCombo.addItems(envs.get_env_names_by_machine(machine))

    def _on_lsa_user_changed(self, user_name: str) -> None:
        """Handler for the LSA cycle selection."""
        context_name = self.lsaSelector.selected_context.name
        LOG.debug("cycle changed: %s, %s", context_name, user_name)
        self.last_lsa_selection[self.accelerator] = user_name
        current_env_name = self.environmentCombo.currentText()
        self._on_env_changed(current_env_name)

    def _on_env_changed(self, env_name: str) -> None:
        """Handler for the environment selection."""
        LOG.debug("environment changed: %s", env_name)
        self._update_env(None)
        if not env_name:
            return
        please_wait_dialog = CreatingEnvDialog(self.window())
        please_wait_dialog.show()
        try:
            env = envs.make_env_by_name(env_name, self._make_japc)
        except:  # pylint: disable=bare-except
            LOG.error(traceback.format_exc())
            LOG.error("Aborted initialization due to the above exception")
            env = None
        please_wait_dialog.accept()
        please_wait_dialog.setParent(None)
        LOG.debug("new environment: %s", env)
        self._update_env(env)

    def _on_algo_changed(
        self, algo_class: t.Optional[t.Type[single_opt.BaseOptimizer]]
    ) -> None:
        """Handler for the algorithm selection."""
        self.opt_runner.set_optimizer_class(algo_class)
        LOG.debug("new algorithm: %s", self.opt_runner.optimizer)
        self.configOptButton.setEnabled(
            isinstance(self.opt_runner.optimizer, coi.Configurable)
        )

    def _on_config_env(self) -> None:
        """Handler for the env configuration."""
        env = self.opt_runner.problem
        if not _is_env_configurable(env):
            LOG.error("not configurable: %s", env.unwrapped)
            return
        dialog = ProblemConfigureDialog(
            env,
            skeleton_points=self.opt_runner.skeleton_points,
            parent=self.window(),
        )
        name = type(env.unwrapped).__name__
        dialog.setWindowTitle(f"Configure {name} ...")
        dialog.skeleton_points_updated.connect(self.opt_runner.set_skeleton_points)
        dialog.open()

    def _on_config_algo(self) -> None:
        """Handler for the algorith, configuration."""
        algo = getattr(self.opt_runner, "optimizer", None)
        if not isinstance(algo, coi.Configurable):
            LOG.error("not configurable: %s", algo)
            return
        dialog = PureConfigureDialog(algo, self.window())
        dialog.setWindowTitle(f"Configure {type(algo).__name__} ...")
        dialog.open()

    def _on_launch_clicked(self) -> None:
        """Handler for the Launch button."""
        if not self.opt_runner.is_ready_to_run():
            LOG.error("cannot launch, optimizer is missing configuration")
            return
        LOG.debug("launching ...")
        self.launchButton.setEnabled(False)
        self.resetButton.setEnabled(False)
        self.stopButton.setEnabled(True)
        self._add_render_output()
        job = self.opt_runner.create_job()
        threadpool = QtCore.QThreadPool.globalInstance()
        threadpool.start(job)

    def _on_stop_clicked(self) -> None:
        """Handler for the Stop button."""
        if self.opt_runner.last_job is None:
            LOG.error("no job to cancel")
            return
        LOG.debug("stopping ...")
        self.stopButton.setEnabled(False)
        self.opt_runner.last_job.cancel()

    def _on_reset_clicked(self) -> None:
        """Handler for the Reset button."""
        job = self.opt_runner.last_job
        if job is None:
            LOG.error("cannot reset %s, no job has been run", self.opt_runner.problem)
            return
        LOG.debug("resetting %s ...", self.opt_runner.problem)
        job.reset()
        env = self.opt_runner.problem
        assert env is not None
        if "matplotlib_figures" in env.metadata.get("render.modes", []):
            env.render(mode="matplotlib_figures")
            self.plot_manager.redraw_mpl_figures()

    def _on_finished(self) -> None:
        """Handler for when optimization is finished."""
        LOG.info("optimization finished")
        self.launchButton.setEnabled(True)
        self.resetButton.setEnabled(True)
        self.stopButton.setEnabled(False)

    def _add_render_output(self) -> None:
        env = self.opt_runner.problem
        assert env is not None
        render_modes = env.metadata.get("render.modes", [])
        if "matplotlib_figures" in render_modes:
            figures = env.render(mode="matplotlib_figures")
            self.plot_manager.replace_mpl_figures(figures)
        else:
            self.plot_manager.clear_mpl_figures()


def _is_env_configurable(env: coi.Problem) -> bool:
    return isinstance(
        env.unwrapped,
        (coi.Configurable, coi_funcs.FunctionOptimizable),
    )
