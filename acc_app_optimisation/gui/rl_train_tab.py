import contextlib
import traceback
import typing as t
from logging import getLogger

import gym
from cernml import coi
from PyQt5 import QtCore, QtGui, QtWidgets

from ..envs import iter_env_names
from ..job_control import train_rl
from . import configuration
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


class RlTrainTab(QtWidgets.QWidget):
    # pylint: disable = too-many-instance-attributes

    def __init__(
        self, parent: t.Optional[QtWidgets.QWidget] = None, *, plot_manager: PlotManager
    ) -> None:
        # pylint: disable = too-many-statements
        super().__init__(parent)
        # Set up internal attributes.
        self._machine = coi.Machine.NoMachine
        self._train_builder = train_rl.TrainJobBuilder()
        self._current_train_job: t.Optional[train_rl.TrainJob] = None
        self._plot_manager = plot_manager
        # Bind the job factories signals to the outside world.
        self._train_builder.signals.objective_updated.connect(
            self._plot_manager.set_objective_curve_data
        )
        self._train_builder.signals.actors_updated.connect(
            self._plot_manager.set_actors_curve_data
        )
        self._train_builder.signals.reward_lists_updated.connect(
            self._plot_manager.set_reward_curve_data
        )
        self._train_builder.signals.training_finished.connect(
            self._on_training_finished
        )
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
        self.algo_combo.addItem("TD3")
        self.setMachine(self._machine)

    @contextlib.contextmanager
    def create_lsa_context(self, japc: "PyJapc") -> t.Iterator[None]:
        assert self._train_builder.japc is None, "nested LSA context"
        self._train_builder.japc = japc
        try:
            yield
        finally:
            self._train_builder.unload_env()
            self._train_builder.japc = None

    def get_or_load_env(self) -> gym.Env:
        if self._train_builder.env is not None:
            return self._train_builder.env
        please_wait_dialog = CreatingEnvDialog(self.window())
        please_wait_dialog.show()
        try:
            LOG.debug("initializing new problem: %s", self._train_builder.env_id)
            return self._train_builder.make_env()
        except:  # pylint: disable=bare-except
            LOG.error(traceback.format_exc())
            LOG.error("Aborted initialization due to the above exception")
            return None
        finally:
            please_wait_dialog.accept()
            please_wait_dialog.setParent(None)  # type: ignore

    def machine(self) -> coi.Machine:
        return self._machine

    def setMachine(self, machine: coi.Machine) -> None:  # pylint: disable=invalid-name
        self._machine = machine
        self.env_combo.clear()
        self.env_combo.addItems(iter_env_names(machine=machine, superclass=gym.Env))

    def _on_env_changed(self, name: str) -> None:
        self._train_builder.env_id = name
        self._clear_job()

    def _on_env_config_clicked(self) -> None:
        env = self.get_or_load_env()
        if env is None:
            # Initialization failed, logs already made.
            return
        dialog = configuration.EnvDialog(
            env, self._train_builder.time_limit, parent=self.window()
        )
        dialog.config_applied.connect(lambda: self._set_time_limit(dialog.timeLimit()))
        dialog.open()

    def _set_time_limit(self, time_limit: int) -> None:
        LOG.info("new time limit: %s", time_limit)
        self._train_builder.time_limit = time_limit

    def _on_algo_changed(self, name: str) -> None:
        factory = train_rl.ALL_AGENTS[name]
        self._train_builder.agent_factory = factory()
        self.algo_config_button.setEnabled(issubclass(factory, coi.Configurable))

    def _on_algo_config_clicked(self) -> None:
        factory = self._train_builder.agent_factory
        if not isinstance(factory, coi.Configurable):
            LOG.error("not configurable: %s", factory)
            return
        dialog = configuration.PureDialog(factory, self.window())
        dialog.open()

    def _on_start_clicked(self) -> None:
        env = self.get_or_load_env()
        if env is None:
            return
        self._current_train_job = self._train_builder.build_job()
        assert self._current_train_job is not None
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.save_button.setEnabled(False)
        self._add_render_output(env)
        threadpool = QtCore.QThreadPool.globalInstance()
        threadpool.start(self._current_train_job)

    def _on_stop_clicked(self) -> None:
        if self._current_train_job is None:
            LOG.error("there is nothing to stop")
            return
        LOG.debug("stopping ...")
        self.stop_button.setEnabled(False)
        self._current_train_job.cancel()

    def _on_training_finished(self) -> None:
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.save_button.setEnabled(True)

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
        render_modes = problem.metadata.get("render.modes", [])
        if "matplotlib_figures" in render_modes:
            figures = problem.render(mode="matplotlib_figures")
            self._plot_manager.replace_mpl_figures(figures)
        else:
            self._plot_manager.clear_mpl_figures()
