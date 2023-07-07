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

import gym
from cernml import coi
from PyQt5 import QtCore, QtGui, QtWidgets

from .. import envs
from .. import lsa_utils_hooks as _hooks
from ..job_control import rl
from ..utils.typecheck import is_configurable
from . import configuration
from .excdialog import current_exception_dialog, exception_dialog
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


class RlTrainTab(QtWidgets.QWidget):
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
        self._train_builder = rl.TrainJobBuilder()
        self._current_train_job: t.Optional[rl.TrainJob] = None
        self._plot_manager = plot_manager
        self._lsa_hooks = lsa_hooks
        # Bind the job factories signals to the outside world.
        self._train_builder.signals.new_run_started.connect(self._on_training_started)
        self._train_builder.signals.new_run_started.connect(
            lambda metadata: self._plot_manager.reset_default_plots(
                objective_name=metadata.objective_name,
                actor_names=metadata.param_names,
                constraint_names=(),
            )
        )
        self._train_builder.signals.objective_updated.connect(
            self._plot_manager.set_objective_curve_data
        )
        self._train_builder.signals.actors_updated.connect(
            self._plot_manager.set_actors_curve_data
        )
        self._train_builder.signals.reward_lists_updated.connect(
            self._plot_manager.set_reward_curve_data
        )
        self._train_builder.signals.new_episode_started.connect(
            self._on_training_episode_started
        )
        self._train_builder.signals.step_started.connect(self._on_training_step_started)
        self._train_builder.signals.run_finished.connect(self._on_training_finished)
        self._train_builder.signals.run_failed.connect(self._on_training_failed)
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
        self.algo_config_button = QtWidgets.QPushButton("Configure")
        self.algo_config_button.setEnabled(False)
        self.algo_config_button.clicked.connect(self._on_algo_config_clicked)
        separator = QtWidgets.QFrame()
        separator.setFrameStyle(QtWidgets.QFrame.HLine | QtWidgets.QFrame.Sunken)
        self.start_button = QtWidgets.QPushButton("Start")
        self.start_button.clicked.connect(self._on_start_clicked)
        self.stop_button = QtWidgets.QPushButton("Stop")
        self.stop_button.clicked.connect(self._on_stop_clicked)
        self.stop_button.setEnabled(False)
        self.save_button = QtWidgets.QPushButton("Save")
        self.save_button.clicked.connect(self._on_save_clicked)
        self.save_button.setEnabled(False)
        # Lay out all widgets.
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(env_label)
        layout.addWidget(self.env_combo)
        layout.addWidget(self.env_config_button)
        layout.addWidget(algo_label)
        layout.addWidget(self.algo_combo)
        layout.addWidget(self.algo_config_button)
        layout.addWidget(separator)
        run_control = QtWidgets.QHBoxLayout()
        run_control.setContentsMargins(0, 0, 0, 0)
        run_control.addWidget(self.start_button)
        run_control.addWidget(self.stop_button)
        run_control.addWidget(self.save_button)
        layout.addLayout(run_control)
        # Fill all GUI elements, fire any events based on that.
        self.algo_combo.addItems(rl.ALL_AGENTS.keys())
        self.setMachine(self._machine)

    @contextlib.contextmanager
    def create_lsa_context(self, japc: "PyJapc") -> t.Iterator[None]:
        assert self._train_builder.japc is None, "nested LSA context"
        self._train_builder.japc = japc
        try:
            yield
        finally:
            self._lsa_hooks.update_problem_state(
                _hooks.Closing(), problem=self._train_builder.env_id
            )
            self._train_builder.unload_env()
            self._train_builder.japc = None

    def get_or_load_env(self) -> gym.Env:
        if self._train_builder.env is not None:
            return self._train_builder.env
        please_wait_dialog = CreatingEnvDialog(self.window())
        please_wait_dialog.show()
        try:
            LOG.debug("initializing new problem: %s", self._train_builder.env_id)
            self._lsa_hooks.update_problem_state(
                _hooks.Constructing(), problem=self._train_builder.env_id
            )
            return self._train_builder.make_env()
        except:  # pylint: disable=bare-except
            LOG.error("aborted initialization", exc_info=True)
            current_exception_dialog(
                title="RL training",
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
            _hooks.Closing(), problem=self._train_builder.env_id
        )
        self._train_builder.env_id = name
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
            _hooks.Configuring(), problem=self._train_builder.env_id
        )
        dialog = configuration.EnvDialog(
            env, self._train_builder.time_limit, parent=self.window()
        )
        dialog.config_applied.connect(lambda: self._set_time_limit(dialog.timeLimit()))
        dialog.open()

    def _set_time_limit(self, time_limit: int) -> None:
        LOG.info("new time limit: %s", time_limit)
        self._train_builder.time_limit = time_limit

    def _on_algo_changed(self, name: str) -> None:
        factory = rl.ALL_AGENTS[name]
        self._train_builder.agent_factory = factory()
        self.algo_config_button.setEnabled(issubclass(factory, coi.Configurable))

    def _on_algo_config_clicked(self) -> None:
        factory = self._train_builder.agent_factory
        if not is_configurable(factory):
            LOG.error("not configurable: %s", factory)
            return
        dialog = configuration.PureDialog(factory, self.window())
        dialog.open()

    def _on_start_clicked(self) -> None:
        # Let `self.get_or_load_env()` create the Env object so that we
        # get a please-wait dialog. `build_job()` would also create it,
        # but without visual feedback.
        env = self.get_or_load_env()
        if env is None:
            return
        try:
            # No need for `self._lsa_hooks.update_problem_state()` here,
            # TrainJobBuilder does not run user code.
            self._current_train_job = self._train_builder.build_job()
        except:  # pylint: disable=bare-except
            LOG.error("aborted initialization", exc_info=True)
            current_exception_dialog(
                title="RL training",
                text="The environment could not be initialized due to an exception",
                parent=self.window(),
            ).show()
            return
        assert self._current_train_job is not None
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.save_button.setEnabled(False)
        self._add_render_output(env)
        threadpool = QtCore.QThreadPool.globalInstance()
        threadpool.start(self._current_train_job)

    def _on_training_started(self, metadata: rl.PreRunMetadata) -> None:
        # This is called right before `agent.learn(total_timesteps)`,
        # i.e. before the first reset. `StartingEpisode` is as good a
        # state to switch to as any.
        # CAREFUL: we set `episode=0` and `total_step=0` and rely on
        # `_on_training_episode_started()` and
        # `_on_training_step_started()` to increase them to 1, the first
        # episode and the first step. This means that during the first
        # `reset()`, `total_step` is invalid. This is fine, however,
        # because `StartingEpisode` documents that it only carries
        # `total_step` through and does not use it.
        assert metadata.total_timesteps is not None, "set by AgentFactory"
        self._lsa_hooks.update_problem_state(
            _hooks.StartingEpisode(
                episode=_hooks.LimitedInt(0),
                max_step_per_episode=metadata.time_limit,
                total_step=_hooks.LimitedInt(0, metadata.total_timesteps),
            ),
            problem=metadata.env_id,
        )

    def _on_training_episode_started(self) -> None:
        prev = self._lsa_hooks.problem_state
        if isinstance(prev, _hooks.StartingEpisode):
            # This is the case on the first reset() of a training run.
            state = dataclasses.replace(
                prev,
                episode=prev.episode.incremented(),
            )
        elif isinstance(prev, _hooks.RlTraining):
            # This is the case on each subsequent reset().
            state = prev.restarted()
        else:
            LOG.error("unexpected state in _on_training_episode_started: %r", prev)
            state = _hooks.StartingEpisode(
                episode=_hooks.LimitedInt(1),
                max_step_per_episode=None,
                total_step=None,
            )
        self._lsa_hooks.update_problem_state(state, problem=self._train_builder.env_id)

    def _on_training_step_started(self) -> None:
        prev = self._lsa_hooks.problem_state
        if isinstance(prev, _hooks.StartingEpisode):
            # This is the case on the first step() of an episode.
            state = _hooks.RlTraining(
                step=_hooks.LimitedInt(1, prev.max_step_per_episode),
                total_step=prev.total_step or _hooks.LimitedInt(1),
                episode=prev.episode,
            )
        elif isinstance(prev, _hooks.RlTraining):
            # This is the case on each subsequent step().
            state = prev.incremented_step()
        else:
            LOG.error("unexpected state in _on_training_episode_started: %r", prev)
            state = _hooks.RlTraining(
                step=_hooks.LimitedInt(1),
                total_step=_hooks.LimitedInt(1),
                episode=_hooks.LimitedInt(1),
            )
        self._lsa_hooks.update_problem_state(state, problem=self._train_builder.env_id)

    def _on_stop_clicked(self) -> None:
        if self._current_train_job is None:
            LOG.error("there is nothing to stop")
            return
        LOG.debug("stopping ...")
        self.stop_button.setEnabled(False)
        self._current_train_job.cancel()

    def _on_training_finished(self, success: bool) -> None:
        if success:
            QtWidgets.QMessageBox(
                QtWidgets.QMessageBox.Information,
                "RL training",
                "Job has terminated successfully.",
                parent=self.window(),
            ).show()
        self._lsa_hooks.update_problem_state(None, problem=self._train_builder.env_id)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.save_button.setEnabled(True)

    def _on_training_failed(self, exception: TracebackException) -> None:
        exception_dialog(
            exception,
            title="RL training",
            text="The training failed due to an exception",
            parent=self.window(),
        ).show()
        self._on_training_finished(False)

    def _on_save_clicked(self) -> None:
        dialog = QtWidgets.QFileDialog(self.window())
        dialog.setAcceptMode(dialog.AcceptSave)
        dialog.setFileMode(dialog.AnyFile)
        dialog.setModal(True)
        dialog.accepted.connect(lambda: self._on_save_model_accepted(dialog))
        dialog.show()

    def _on_save_model_accepted(self, dialog: QtWidgets.QFileDialog) -> None:
        if self._current_train_job is None:
            LOG.error("there is nothing to save")
            return
        [path] = dialog.selectedFiles()
        LOG.info("saving: %s", path)
        self._current_train_job.save(path)

    def _clear_job(self) -> None:
        self._current_train_job = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.save_button.setEnabled(False)

    def _add_render_output(self, problem: coi.Problem) -> None:
        if "matplotlib_figures" in envs.Metadata(problem).render_modes:
            figures = problem.render(mode="matplotlib_figures")
            self._plot_manager.replace_mpl_figures(figures)
        else:
            self._plot_manager.clear_mpl_figures()
