# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

from __future__ import annotations

import contextlib
import dataclasses
import typing as t
from logging import getLogger
from pathlib import Path

import gym
from cernml import coi
from PyQt5 import QtCore, QtGui, QtWidgets

from .. import envs
from .. import lsa_utils_hooks as _hooks
from ..job_control import rl
from . import configuration
from .excdialog import current_exception_dialog, exception_dialog
from .file_selector import FileSelector
from .plot_manager import PlotManager

if t.TYPE_CHECKING:
    # pylint: disable=import-error, unused-import, ungrouped-imports
    from traceback import TracebackException

    from pyjapc import PyJapc

LOG = getLogger(__name__)


class CreatingEnvDialog(QtWidgets.QDialog):
    """A button-less dialog that tells the user to wait."""

    def __init__(self, parent: t.Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(
            QtWidgets.QLabel("Environment is being initialized, please wait ...")
        )


class RlExecTab(QtWidgets.QWidget):
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
        self._exec_builder = rl.ExecJobBuilder()
        self._current_exec_job: t.Optional[rl.ExecJob] = None
        self._plot_manager = plot_manager
        self._lsa_hooks = lsa_hooks
        # Bind the job factories signals to the outside world.
        self._exec_builder.signals.new_run_started.connect(self._on_run_started)
        self._exec_builder.signals.new_run_started.connect(
            lambda metadata: self._plot_manager.reset_default_plots(
                objective_name=metadata.objective_name,
                actor_names=metadata.param_names,
                constraint_names=(),
            )
        )
        self._exec_builder.signals.objective_updated.connect(
            self._plot_manager.set_objective_curve_data
        )
        self._exec_builder.signals.actors_updated.connect(
            self._plot_manager.set_actors_curve_data
        )
        self._exec_builder.signals.reward_lists_updated.connect(
            self._plot_manager.set_reward_curve_data
        )
        self._exec_builder.signals.new_episode_started.connect(
            self._on_run_episode_started
        )
        self._exec_builder.signals.step_started.connect(self._on_run_step_started)
        self._exec_builder.signals.run_finished.connect(self._on_run_finished)
        self._exec_builder.signals.run_failed.connect(self._on_run_failed)
        # Build the GUI.
        large = QtGui.QFont()
        large.setPointSize(12)
        env_label = QtWidgets.QLabel("Environment")
        env_label.setFont(large)
        self.env_combo = QtWidgets.QComboBox()
        self.env_combo.currentTextChanged.connect(self._on_env_changed)
        self.env_config_button = QtWidgets.QPushButton("Configure")
        self.env_config_button.clicked.connect(self._on_env_config_clicked)
        algo_label = QtWidgets.QLabel("Algorithm")
        algo_label.setFont(large)
        self.algo_combo = QtWidgets.QComboBox()
        self.algo_combo.currentTextChanged.connect(self._on_algo_changed)
        self.algo_file_selector = FileSelector()
        self.algo_file_selector.setMimeTypeFilters(
            ["application/zip", "application/octet-stream"]
        )
        self.algo_file_selector.fileChanged.connect(self._on_model_file_changed)
        separator = QtWidgets.QFrame()
        separator.setFrameStyle(QtWidgets.QFrame.HLine | QtWidgets.QFrame.Sunken)
        episodes_label = QtWidgets.QLabel("Episodes:")
        episodes_spin = QtWidgets.QSpinBox()
        episodes_spin.valueChanged.connect(self._on_num_episodes_changed)
        episodes_spin.setMinimum(1)
        episodes_spin.setValue(1)
        self.start_button = QtWidgets.QPushButton("Start")
        self.start_button.clicked.connect(self._on_start_clicked)
        self.stop_button = QtWidgets.QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._on_stop_clicked)
        # Lay out all widgets.
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(env_label)
        layout.addWidget(self.env_combo)
        layout.addWidget(self.env_config_button)
        layout.addWidget(algo_label)
        layout.addWidget(self.algo_combo)
        layout.addWidget(self.algo_file_selector)
        layout.addWidget(separator)
        episodes_control = QtWidgets.QHBoxLayout()
        episodes_control.addWidget(episodes_label)
        episodes_control.addWidget(episodes_spin, 1)
        layout.addLayout(episodes_control)
        run_control = QtWidgets.QHBoxLayout()
        run_control.setContentsMargins(0, 0, 0, 0)
        run_control.addWidget(self.start_button)
        run_control.addWidget(self.stop_button)
        layout.addLayout(run_control)
        # Fill all GUI elements, fire any events based on that.
        self.algo_combo.addItems(rl.ALL_AGENTS.keys())
        self.setMachine(self._machine)

    @contextlib.contextmanager
    def create_lsa_context(self, japc: PyJapc) -> t.Iterator[None]:
        assert self._exec_builder.japc is None, "nested LSA context"
        self._exec_builder.japc = japc
        try:
            yield
        finally:
            self._lsa_hooks.update_problem_state(
                _hooks.Closing(), problem=self._exec_builder.env_id
            )
            self._exec_builder.unload_env()
            self._exec_builder.japc = None

    def get_or_load_env(self) -> gym.Env:
        if self._exec_builder.env is not None:
            return self._exec_builder.env
        please_wait_dialog = CreatingEnvDialog(self.window())
        please_wait_dialog.show()
        try:
            LOG.debug("initializing new problem: %s", self._exec_builder.env_id)
            self._lsa_hooks.update_problem_state(
                _hooks.Constructing(), problem=self._exec_builder.env_id
            )
            return self._exec_builder.make_env()
        except:  # pylint: disable=bare-except
            LOG.error("aborted initialization", exc_info=True)
            current_exception_dialog(
                title="RL run",
                text="The environment could not be initialized due to an exception",
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
            envs.iter_env_names(machine=machine, superclass=gym.Env)
        )

    def _on_env_changed(self, name: str) -> None:
        self._lsa_hooks.update_problem_state(
            _hooks.Closing(), problem=self._exec_builder.env_id
        )
        self._exec_builder.env_id = name
        self._lsa_hooks.update_problem(name)
        self._clear_job()
        enable_config_button = False
        if name:
            env_spec = coi.spec(name)
            # TODO: This does not work well with wrappers.
            env_class = env_spec.entry_point
            enable_config_button = issubclass(env_class, coi.Configurable)
        self.env_config_button.setEnabled(enable_config_button)
        LOG.debug("configurable: %s", enable_config_button)

    def _on_env_config_clicked(self) -> None:
        env = self.get_or_load_env()
        if env is None:
            # Initialization failed, logs already made.
            return
        self._lsa_hooks.update_problem_state(
            _hooks.Configuring(), problem=self._exec_builder.env_id
        )
        dialog = configuration.EnvDialog(
            env, self._exec_builder.time_limit, parent=self.window()
        )
        dialog.config_applied.connect(lambda: self._set_time_limit(dialog.timeLimit()))
        dialog.open()

    def _set_time_limit(self, time_limit: int) -> None:
        LOG.info("new time limit: %s", time_limit)
        self._exec_builder.time_limit = time_limit

    def _on_algo_changed(self, name: str) -> None:
        factory = rl.ALL_AGENTS[name]
        self._exec_builder.agent_factory = factory()
        self._exec_builder.agent_path = None
        self.algo_file_selector.setFilePath("")

    def _on_model_file_changed(self, path: str) -> None:
        if path:
            LOG.info("selected model file: %r", path)
            self._exec_builder.agent_path = Path(path)
        else:
            LOG.info("no model file selected")
            self._exec_builder.agent_path = None

    def _on_start_clicked(self) -> None:
        # Let `self.get_or_load_env()` create the Env object so that we
        # get a please-wait dialog. `build_job()` would also create it,
        # but without visual feedback.
        env = self.get_or_load_env()
        if env is None:
            return
        try:
            # No need for `self._lsa_hooks.update_problem_state()` here,
            # ExecJobBuilder does not run user code.
            self._current_exec_job = self._exec_builder.build_job()
        except:  # pylint: disable=bare-except
            LOG.error("aborted initialization", exc_info=True)
            current_exception_dialog(
                title="RL run",
                text="The environment could not be initialized due to an exception",
                parent=self.window(),
            ).show()
            return
        assert self._current_exec_job is not None
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self._add_render_output(env)
        threadpool = QtCore.QThreadPool.globalInstance()
        threadpool.start(self._current_exec_job)

    def _on_run_started(self, metadata: rl.PreRunMetadata) -> None:
        # This is called right before the execution loop, i.e. before
        # the first reset. `StartingEpisode` is as good a state to
        # switch to as any.
        # CAREFUL: we set `episode=0` and rely on
        # `_on_training_episode_started()` to increase it to 1, the
        # first episode.
        self._lsa_hooks.update_problem_state(
            _hooks.StartingEpisode(
                episode=_hooks.LimitedInt(0),
                max_step_per_episode=metadata.time_limit,
                total_step=_hooks.LimitedInt(0, metadata.total_timesteps),
            ),
            problem=metadata.env_id,
        )

    def _on_run_episode_started(self) -> None:
        prev = self._lsa_hooks.problem_state
        if isinstance(prev, _hooks.StartingEpisode):
            # This is the case on the first reset() of a run.
            state = dataclasses.replace(
                prev,
                episode=prev.episode.incremented(),
            )
        elif isinstance(prev, _hooks.Optimizing):
            # This is the case on each subsequent reset().
            if prev.episode is None:
                LOG.error("no episode information: %r", prev)
                episode = _hooks.LimitedInt(1)
            else:
                episode = prev.episode.incremented()
            state = _hooks.StartingEpisode(
                episode=episode,
                max_step_per_episode=prev.step.max,
                total_step=prev.total_step,
            )
        else:
            LOG.error("unexpected state in _on_training_episode_started: %r", prev)
            state = _hooks.StartingEpisode(
                episode=_hooks.LimitedInt(1),
                max_step_per_episode=None,
                total_step=None,
            )
        self._lsa_hooks.update_problem_state(state, problem=self._exec_builder.env_id)

    def _on_run_step_started(self) -> None:
        prev = self._lsa_hooks.problem_state
        if isinstance(prev, _hooks.StartingEpisode):
            # This is the case on the first step() of an episode.
            state = _hooks.Optimizing(
                step=_hooks.LimitedInt(1, prev.max_step_per_episode),
                total_step=prev.total_step or _hooks.LimitedInt(1),
                episode=prev.episode,
            )
        elif isinstance(prev, _hooks.Optimizing):
            # This is the case on each subsequent step().
            state = prev.incremented_step()
        else:
            LOG.error("unexpected state in _on_training_episode_started: %r", prev)
            state = _hooks.Optimizing(
                step=_hooks.LimitedInt(1),
                total_step=_hooks.LimitedInt(1),
                episode=_hooks.LimitedInt(1),
            )
        self._lsa_hooks.update_problem_state(state, problem=self._exec_builder.env_id)

    def _on_stop_clicked(self) -> None:
        if self._current_exec_job is None:
            LOG.error("there is nothing to stop")
            return
        LOG.debug("stopping ...")
        self.stop_button.setEnabled(False)
        self._current_exec_job.cancel()

    def _on_run_finished(self, success: bool) -> None:
        if success:
            QtWidgets.QMessageBox(
                QtWidgets.QMessageBox.Information,
                "RL run",
                "Job has terminated successfully.",
                parent=self.window(),
            ).show()
        self._lsa_hooks.update_problem_state(None, problem=self._exec_builder.env_id)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def _on_run_failed(self, exception: TracebackException) -> None:
        exception_dialog(
            exception,
            title="RL run",
            text="The run failed due to an exception",
            parent=self.window(),
        ).show()
        self._on_run_finished(False)

    def _clear_job(self) -> None:
        self._current_exec_job = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def _on_num_episodes_changed(self, value: int) -> None:
        self._exec_builder.num_episodes = value

    def _add_render_output(self, problem: coi.Problem) -> None:
        if "matplotlib_figures" in envs.Metadata(problem).render_modes:
            figures = problem.render(mode="matplotlib_figures")
            self._plot_manager.replace_mpl_figures(figures)
        else:
            self._plot_manager.clear_mpl_figures()
