# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

from __future__ import annotations

import contextlib
import dataclasses
import enum
import typing as t
from logging import getLogger

import numpy as np
from cernml import coi, optimizers
from PyQt5 import QtCore, QtGui, QtWidgets

from .. import envs
from .. import lsa_utils_hooks as _hooks
from ..job_control.single_objective import OptJob, OptJobBuilder
from ..utils.typecheck import (
    AnyOptimizable,
    is_any_optimizable,
    is_configurable,
    is_function_optimizable,
)
from . import configuration
from .excdialog import current_exception_dialog, exception_dialog
from .plot_manager import PlotManager
from .task import ThreadPoolTask

if t.TYPE_CHECKING:
    # pylint: disable=import-error, unused-import, ungrouped-imports
    from traceback import TracebackException

    from gym.envs.registration import EnvSpec
    from pyjapc import PyJapc

    from ..job_control.single_objective.jobs import (
        PreOptimizationMetadata,
        PreStepMetadata,
    )


LOG = getLogger(__name__)


class CreatingEnvDialog(QtWidgets.QDialog):
    """A button-less dialog that tells the user to wait."""

    def __init__(self, parent: t.Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(
            QtWidgets.QLabel("Environment is being initialized, please wait ...")
        )


class ConfirmationDialog(QtWidgets.QDialog):
    """Qt dialog to show a job's reset point and ask for confirmation.

    Args:
        job: The job about to be reset.
        parent: The parent widget to attach to.
    """

    def __init__(
        self, job: OptJob, parent: t.Optional[QtWidgets.QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Reset")
        self.setModal(True)
        layout = QtWidgets.QGridLayout(self)
        icon = QtWidgets.QLabel()
        icon.setPixmap(
            QtWidgets.QMessageBox.standardIcon(QtWidgets.QMessageBox.Information)
        )
        layout.addWidget(icon, 0, 0, 1, 1, QtCore.Qt.AlignTop)
        label = QtWidgets.QLabel(
            "Do you want to reset the problem to the following point?"
        )
        layout.addWidget(label, 0, 1, 1, 1)
        details = QtWidgets.QTextEdit()
        details.setPlainText(job.format_reset_point())
        details.setMinimumHeight(100)
        details.setFocusPolicy(QtCore.Qt.NoFocus)
        details.setReadOnly(True)
        layout.addWidget(details, 1, 0, 1, 2)
        buttons = QtWidgets.QDialogButtonBox(
            t.cast(
                QtWidgets.QDialogButtonBox.StandardButtons,
                QtWidgets.QDialogButtonBox.Yes | QtWidgets.QDialogButtonBox.No,
            )
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons, 2, 1, 1, 1)
        # Set this default _after_ `addWidget()`, lest Qt ignores it.
        no_button = buttons.button(QtWidgets.QDialogButtonBox.No)
        no_button.setDefault(True)
        no_button.setFocus()


class RunControlButtons(QtWidgets.QWidget):
    """Row of buttons to start/stop/reset a run."""

    @enum.unique
    class State(enum.Enum):
        READY = "ready"
        RUNNING = "running"
        STOPPING = "stopping"
        FINISHED = "finished"

    def __init__(self, parent: t.Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.start = QtWidgets.QPushButton("Start")
        self.stop = QtWidgets.QPushButton("Stop")
        self.reset = QtWidgets.QPushButton("Reset")
        self.export = QtWidgets.QPushButton("Export")
        self.stop.setEnabled(False)
        self.reset.setEnabled(False)
        self.export.setEnabled(False)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.start)
        layout.addWidget(self.stop)
        layout.addWidget(self.reset)
        layout.addWidget(self.export)

    def transition(self, state: State) -> None:
        State = self.State
        if state == State.READY:
            self.start.setEnabled(True)
            self.stop.setEnabled(False)
            self.reset.setEnabled(False)
            self.export.setEnabled(False)
        elif state == State.RUNNING:
            self.start.setEnabled(False)
            self.stop.setEnabled(True)
            self.reset.setEnabled(False)
            self.export.setEnabled(False)
        elif state == State.STOPPING:
            self.start.setEnabled(False)
            self.stop.setEnabled(False)
            self.reset.setEnabled(False)
            self.export.setEnabled(False)
        elif state == State.FINISHED:
            self.start.setEnabled(True)
            self.stop.setEnabled(False)
            self.reset.setEnabled(True)
            self.export.setEnabled(True)
        else:
            raise ValueError(f"expected State object, got {state!r}")


class NumOptTab(QtWidgets.QWidget):
    def __init__(
        self,
        parent: t.Optional[QtWidgets.QWidget] = None,
        *,
        lsa_hooks: _hooks.GeoffHooks,
        plot_manager: PlotManager,
    ) -> None:
        # pylint: disable = too-many-statements
        super().__init__(parent)
        # Set up internal attributes.
        self._machine = coi.Machine.NO_MACHINE
        self._opt_job_builder = OptJobBuilder()
        self._current_opt_job: t.Optional[OptJob] = None
        self._plot_manager = plot_manager
        self._lsa_hooks = lsa_hooks
        self._custom_optimizers: t.Mapping[str, optimizers.Optimizer] = {}
        # Bind the job factories signals to the outside world.
        self._opt_job_builder.signals.new_optimisation_started.connect(
            self._on_optimization_started
        )
        self._opt_job_builder.signals.new_optimisation_started.connect(
            lambda metadata: self._plot_manager.reset_default_plots(
                objective_name=metadata.objective_name,
                actor_names=metadata.param_names,
                constraint_names=metadata.constraint_names,
            )
        )
        self._opt_job_builder.signals.objective_updated.connect(
            self._plot_manager.set_objective_curve_data
        )
        self._opt_job_builder.signals.actors_updated.connect(
            self._plot_manager.set_actors_curve_data
        )
        self._opt_job_builder.signals.constraints_updated.connect(
            self._plot_manager.set_constraints_curve_data
        )
        self._opt_job_builder.signals.new_skeleton_point_selected.connect(
            self._on_optimization_new_skeleton_point_selected
        )
        self._opt_job_builder.signals.step_started.connect(
            self._on_optimization_step_started
        )
        self._opt_job_builder.signals.optimisation_finished.connect(
            self._on_opt_finished
        )
        self._opt_job_builder.signals.optimisation_failed.connect(self._on_opt_failed)
        # Build the GUI.
        large = QtGui.QFont()
        large.setPointSize(12)
        env_label = QtWidgets.QLabel("Environment")
        env_label.setFont(large)
        self.env_combo = QtWidgets.QComboBox()
        self.env_combo.currentTextChanged.connect(self._on_env_changed)
        self.env_config_button = QtWidgets.QPushButton("Configure")
        self.env_config_button.setEnabled(False)
        self.env_config_button.clicked.connect(self._on_env_config_clicked)
        self.constraints_check = QtWidgets.QCheckBox("Show constraints")
        self.constraints_check.toggled.connect(
            self._plot_manager.set_constraints_plot_visible
        )
        algo_label = QtWidgets.QLabel("Algorithm")
        algo_label.setFont(large)
        self.algo_combo = QtWidgets.QComboBox()
        self.algo_combo.currentTextChanged.connect(self._on_algo_changed)
        self.algo_config_button = QtWidgets.QPushButton("Configure")
        self.algo_config_button.setEnabled(False)
        self.algo_config_button.clicked.connect(self._on_algo_config_clicked)
        separator = QtWidgets.QFrame()
        separator.setFrameStyle(QtWidgets.QFrame.HLine | QtWidgets.QFrame.Sunken)
        self.run_ctrl = RunControlButtons(self)
        self.run_ctrl.start.clicked.connect(self._on_start_clicked)
        self.run_ctrl.stop.clicked.connect(self._on_stop_clicked)
        self.run_ctrl.reset.clicked.connect(self._on_reset_clicked)
        self.run_ctrl.export.clicked.connect(self._on_export_clicked)
        # Lay out all widgets.
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(env_label)
        layout.addWidget(self.env_combo)
        layout.addWidget(self.env_config_button)
        layout.addWidget(self.constraints_check)
        layout.addWidget(algo_label)
        layout.addWidget(self.algo_combo)
        layout.addWidget(self.algo_config_button)
        layout.addWidget(separator)
        layout.addWidget(self.run_ctrl)
        # Fill all GUI elements, fire any events based on that.
        self.algo_combo.addItems(optimizers.registry.keys())
        self.setMachine(self._machine)

    @contextlib.contextmanager
    def create_lsa_context(self, japc: PyJapc) -> t.Iterator[None]:
        assert self._opt_job_builder.japc is None, "nested LSA context"
        self._opt_job_builder.japc = japc
        try:
            yield
        finally:
            self._lsa_hooks.update_problem_state(
                _hooks.Closing(), problem=self._opt_job_builder.problem_id
            )
            self._opt_job_builder.unload_problem()
            self._opt_job_builder.japc = None

    def get_or_load_problem(self) -> t.Optional[AnyOptimizable]:
        if self._opt_job_builder.problem is not None:
            return self._opt_job_builder.problem
        please_wait_dialog = CreatingEnvDialog(self.window())
        please_wait_dialog.show()
        try:
            LOG.debug("initializing new problem: %s", self._opt_job_builder.problem_id)
            self._lsa_hooks.update_problem_state(
                _hooks.Constructing(), problem=self._opt_job_builder.problem_id
            )
            return self._opt_job_builder.make_problem()
        except:  # noqa: E722 # pylint: disable=bare-except
            LOG.error("aborted initialization", exc_info=True)
            current_exception_dialog(
                title="Numerical optimization",
                text="The problem could not be initialized due to an exception",
                parent=self.window(),
            ).show()
            return None
        finally:
            please_wait_dialog.accept()
            please_wait_dialog.setParent(None)  # type: ignore

    def machine(self) -> coi.Machine:
        return self._machine

    def setMachine(self, machine: coi.Machine) -> None:  # pylint: disable=invalid-name
        self._machine = machine
        self.env_combo.clear()
        self.env_combo.addItems(
            envs.iter_env_names(
                machine=machine,
                superclass=(coi.SingleOptimizable, coi.FunctionOptimizable),
            )
        )

    def _remove_custom_algos(self) -> None:
        self.algo_combo.clear()
        self._custom_optimizers = {}
        self.algo_combo.addItems(optimizers.registry.keys())

    def _add_custom_algos(self, env_spec: EnvSpec) -> None:
        self._custom_optimizers = envs.get_custom_optimizers(env_spec)
        self.algo_combo.insertItems(0, self._custom_optimizers.keys())

    def _on_env_changed(self, name: str) -> None:
        self._lsa_hooks.update_problem_state(
            _hooks.Closing(), problem=self._opt_job_builder.problem_id
        )
        self._opt_job_builder.problem_id = name
        self._lsa_hooks.update_problem(name)
        self._clear_job()
        enable_config_button = False
        self._remove_custom_algos()
        if name:
            env_spec = coi.spec(name)
            # TODO: This does not work well with wrappers.
            env_class = env_spec.entry_point
            LOG.info("class: %s", env_class)
            enable_config_button = issubclass(
                env_class, (coi.Configurable, coi.FunctionOptimizable)
            )
            LOG.info("config enabled: %s", enable_config_button)
            self._add_custom_algos(env_spec)
        self.env_config_button.setEnabled(enable_config_button)
        LOG.debug("configurable: %s", enable_config_button)

    def _on_env_config_clicked(self) -> None:
        problem = self.get_or_load_problem()
        if problem is None:
            # Initialization failed, logs already made.
            return
        if not is_configurable(problem) and not is_function_optimizable(problem):
            LOG.error("not configurable: %s", problem)
            return
        # Assert to guide MyPy.
        assert isinstance(problem, coi.Problem) and is_any_optimizable(problem)
        self._lsa_hooks.update_problem_state(
            _hooks.Configuring(), problem=self._opt_job_builder.problem_id
        )
        dialog = configuration.OptimizableDialog(
            problem,
            skeleton_points=self._opt_job_builder.skeleton_points,
            parent=self.window(),
        )
        if is_function_optimizable(problem):

            def _set_skeleton_points() -> None:
                skeleton_points = dialog.skeletonPoints()
                assert skeleton_points is not None
                LOG.info("new skeleton points: %s", skeleton_points)
                self._opt_job_builder.skeleton_points = skeleton_points

            dialog.config_applied.connect(_set_skeleton_points)
        dialog.open()

    def _on_algo_changed(self, name: str) -> None:
        opt = self._custom_optimizers.get(name, None)
        if opt is None:
            opt = optimizers.make(name)
        self._opt_job_builder.optimizer = opt
        self.algo_config_button.setEnabled(is_configurable(opt))

    def _on_algo_config_clicked(self) -> None:
        opt = self._opt_job_builder.optimizer
        if not is_configurable(opt):
            LOG.error("not configurable: %s", opt)
            return
        dialog = configuration.PureDialog(opt, self.window())
        dialog.open()

    def _on_start_clicked(self) -> None:
        # Let `self.get_or_load_problem()` create the problem object so
        # that we get a please-wait dialog. `build_job()` would also
        # create it, but without visual feedback.
        problem = self.get_or_load_problem()
        if problem is None:
            return
        try:
            assert self._opt_job_builder.problem is not None
            # If problem is a FunctionOptimizable, set cycle_time later.
            self._lsa_hooks.update_problem_state(
                _hooks.StartingOptimization(cycle_time=None),
                problem=self._opt_job_builder.problem_id,
            )
            self._current_opt_job = self._opt_job_builder.build_job()
        except:  # noqa: E722 # pylint: disable=bare-except
            LOG.error("aborted initialization", exc_info=True)
            current_exception_dialog(
                title="Numerical optimization",
                text="The problem could not be initialized due to an exception",
                parent=self.window(),
            ).show()
            return
        assert self._current_opt_job is not None
        self.run_ctrl.transition(RunControlButtons.State.RUNNING)
        self._add_render_output(problem)
        threadpool = QtCore.QThreadPool.globalInstance()
        threadpool.start(self._current_opt_job)

    def _on_optimization_started(self, metadata: PreOptimizationMetadata) -> None:
        # This is called right before `solve(objective, x0)`, i.e.
        # before all skeleton points. Because *x₀* has already been
        # fetched, we need to switch to state `optimizing()`.
        # CAREFUL: we set `step=0` and rely on
        # `_on_optimization_step_started()` to increase it to 1, the
        # first step.
        # CAREFUL: We reset `cycle_time` to `None` and rely on
        # `_on_optimization_new_skeleton_point_selected()` being called
        # before `_on_optimization_step_started()`.
        self._lsa_hooks.update_problem_state(
            _hooks.Optimizing(
                step=_hooks.LimitedInt(0, metadata.max_function_evaluations)
            ),
            problem=metadata.problem_id,
        )

    def _on_optimization_new_skeleton_point_selected(self, cycle_time: float) -> None:
        # This is called in four different contexts:
        # 1. while fetching x₀ (state is `StartingOptimization`),
        # 2. during reset (state is `Resetting`),
        # 3. at start of optimization (state is `Optimizing(step=0)`),
        # 4. between optimizations for different skeleton points (state
        #    is `FinalStep`).
        # In all four cases, we try to leave the state intact and simply
        # update its `cycle_time`. Any state changes should be done in
        # `_advance_state()`.
        state = self._lsa_hooks.problem_state
        assert isinstance(
            state,
            (
                _hooks.StartingOptimization,
                _hooks.Optimizing,
                _hooks.FinalStep,
                _hooks.Resetting,
            ),
        ), f"new skeleton point chosen in unexpected state: {state!r}"
        state = dataclasses.replace(state, cycle_time=cycle_time)
        self._lsa_hooks.update_problem_state(
            state, problem=self._opt_job_builder.problem_id
        )

    def _on_optimization_step_started(self, metadata: PreStepMetadata) -> None:
        state = _advance_state(self._lsa_hooks.problem_state, metadata.final_step)
        self._lsa_hooks.update_problem_state(
            state, problem=self._opt_job_builder.problem_id
        )

    def _on_stop_clicked(self) -> None:
        if self._current_opt_job is None:
            LOG.error("there is nothing to stop")
            return
        LOG.debug("stopping ...")
        self.run_ctrl.transition(RunControlButtons.State.STOPPING)
        self._current_opt_job.cancel()

    def _on_opt_finished(self, success: bool) -> None:
        if success:
            QtWidgets.QMessageBox(
                QtWidgets.QMessageBox.Information,
                "Numerical optimization",
                "Job has terminated successfully.",
                parent=self.window(),
            ).show()
        self._lsa_hooks.update_problem_state(
            None, problem=self._opt_job_builder.problem_id
        )
        self.run_ctrl.transition(RunControlButtons.State.FINISHED)

    def _on_opt_failed(self, exception: TracebackException) -> None:
        exception_dialog(
            exception,
            title="Numerical optimization",
            text="The optimization failed due to an exception",
            parent=self.window(),
        ).show()
        self._on_opt_finished(False)

    def _on_reset_clicked(self) -> None:
        if self._current_opt_job is None:
            LOG.error("cannot reset, no job has been run")
            return
        # This assignment convinces MyPy that `job` is never None.
        job = self._current_opt_job
        dialog = ConfirmationDialog(job, parent=self)
        dialog.accepted.connect(lambda: self._on_reset_confirmed(job))
        dialog.show()

    def _on_reset_confirmed(self, job: OptJob) -> None:
        LOG.debug("resetting ...")
        self.run_ctrl.transition(RunControlButtons.State.RUNNING)
        threadpool = QtCore.QThreadPool.globalInstance()
        # Note that the cycle time is set by
        # `_on_optimization_new_skeleton_point_selected()`.
        self._lsa_hooks.update_problem_state(
            _hooks.Resetting(1), problem=self._opt_job_builder.problem_id
        )
        # job.reset() does the logging for us and eventually emits
        # another `optimisation_finished` signal.
        threadpool.start(ThreadPoolTask(job.reset))

    def _clear_job(self) -> None:
        self._current_opt_job = None
        self.run_ctrl.transition(RunControlButtons.State.READY)

    def _add_render_output(self, problem: coi.Problem) -> None:
        if "matplotlib_figures" in envs.Metadata(problem).render_modes:
            figures = problem.render(mode="matplotlib_figures")
            self._plot_manager.replace_mpl_figures(figures)
        else:
            self._plot_manager.clear_mpl_figures()

    def _on_export_clicked(self) -> None:
        dialog = QtWidgets.QFileDialog(self.window())
        dialog.setAcceptMode(dialog.AcceptSave)
        dialog.setFileMode(dialog.AnyFile)
        dialog.setModal(True)
        dialog.setDefaultSuffix(".csv")
        dialog.setNameFilters(
            [
                "CSV document (*.csv)",
                "Compressed CSV document (*.csv.gz)",
                "All files (*)",
            ]
        )
        # TODO: Auto-add suffix!
        dialog.accepted.connect(lambda: self._on_export_accepted(dialog))
        dialog.show()

    def _on_export_accepted(self, dialog: QtWidgets.QFileDialog) -> None:
        job = self._current_opt_job
        if job is None:
            LOG.error("there is nothing to save")
            return
        [path] = dialog.selectedFiles()
        LOG.info("saving: %s", path)
        headers = [
            (f"norm_actor_{i}", name) for i, name in enumerate(job.get_param_names(), 1)
        ]
        if job.wrapped_constraints:
            headers.extend(
                (f"constraint_{i}", name)
                for i, name in enumerate(job.get_constraint_names(), 1)
            )
        headers.append(("objective", job.get_objective_name()))
        names, descs = zip(*headers)
        header = f'# {", ".join(names)}\n# {", ".join(descs)}'
        data_blocks = [
            np.array(job.actions_log),
            np.array(job.objectives_log)[:, np.newaxis],
        ]
        if job.wrapped_constraints:
            data_blocks.insert(1, np.array(job.constraints_log))
        np.savetxt(
            path,
            np.hstack(data_blocks),
            header=header,
            comments="",
            delimiter=", ",
            encoding="utf-8",
        )


def _advance_state(prev: t.Optional[_hooks.State], final_step: bool) -> _hooks.State:
    """Helper function to NumOptTab._on_optimization_step_started()."""
    if isinstance(prev, _hooks.Resetting):
        # During resets, the step does not actually change the state.
        return prev
    if isinstance(prev, _hooks.FinalStep):
        # CAREFUL: If we're switching between skeleton points,
        # cycle_time was already updated in
        # `_on_optimization_new_skeleton_point_selected()`.
        LOG.debug("switching state FinalStep to state Optimizing")
        return _hooks.Optimizing(
            step=dataclasses.replace(prev.step, value=1),
            total_step=prev.total_step and prev.total_step.incremented(),
            cycle_time=prev.cycle_time,
        )
    if isinstance(prev, _hooks.Optimizing):
        return prev.finalized() if final_step else prev.incremented_step()
    LOG.fatal("unexpected state in _on_optimization_step_started(): %r", prev)
    return _hooks.Optimizing(_hooks.LimitedInt(1))
