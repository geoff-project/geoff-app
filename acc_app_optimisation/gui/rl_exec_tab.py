import contextlib
import typing as t
from logging import getLogger
from pathlib import Path

import gym
from cernml import coi
from PyQt5 import QtCore, QtGui, QtWidgets

from .. import envs
from ..job_control import rl
from . import configuration
from .file_selector import FileSelector
from .plot_manager import PlotManager

if t.TYPE_CHECKING:
    from pyjapc import PyJapc  # pylint: disable=import-error, unused-import

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
        self, parent: t.Optional[QtWidgets.QWidget] = None, *, plot_manager: PlotManager
    ) -> None:
        # pylint: disable = too-many-statements
        super().__init__(parent)
        # Set up internal attributes.
        self._machine = coi.Machine.NO_MACHINE
        self._exec_builder = rl.ExecJobBuilder()
        self._current_exec_job: t.Optional[rl.ExecJob] = None
        self._plot_manager = plot_manager
        # Bind the job factories signals to the outside world.
        self._exec_builder.signals.new_run_started.connect(
            self._plot_manager.reset_default_plots
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
        self._exec_builder.signals.training_finished.connect(self._on_training_finished)
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
    def create_lsa_context(self, japc: "PyJapc") -> t.Iterator[None]:
        assert self._exec_builder.japc is None, "nested LSA context"
        self._exec_builder.japc = japc
        try:
            yield
        finally:
            self._exec_builder.unload_env()
            self._exec_builder.japc = None

    def get_or_load_env(self) -> gym.Env:
        if self._exec_builder.env is not None:
            return self._exec_builder.env
        please_wait_dialog = CreatingEnvDialog(self.window())
        please_wait_dialog.show()
        try:
            LOG.debug("initializing new problem: %s", self._exec_builder.env_id)
            return self._exec_builder.make_env()
        except:  # pylint: disable=bare-except
            LOG.error("aborted initialization", exc_info=True)
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
        self._exec_builder.env_id = name
        self._clear_job()

    def _on_env_config_clicked(self) -> None:
        env = self.get_or_load_env()
        if env is None:
            # Initialization failed, logs already made.
            return
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
        env = self.get_or_load_env()
        if env is None:
            return
        try:
            self._current_exec_job = self._exec_builder.build_job()
        except:  # pylint: disable=bare-except
            LOG.error("aborted initialization", exc_info=True)
            return
        assert self._current_exec_job is not None
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self._add_render_output(env)
        threadpool = QtCore.QThreadPool.globalInstance()
        threadpool.start(self._current_exec_job)

    def _on_stop_clicked(self) -> None:
        if self._current_exec_job is None:
            LOG.error("there is nothing to stop")
            return
        LOG.debug("stopping ...")
        self.stop_button.setEnabled(False)
        self._current_exec_job.cancel()

    def _on_training_finished(self) -> None:
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

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
