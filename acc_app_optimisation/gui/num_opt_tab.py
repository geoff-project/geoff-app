import contextlib
import traceback
import typing as t
from logging import getLogger

import numpy as np
from cernml import coi, coi_funcs
from PyQt5 import QtCore, QtGui, QtWidgets

from ..job_control.single_objective import OptJob, OptJobBuilder, optimizers
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


class NumOptTab(QtWidgets.QWidget):
    # pylint: disable = too-many-instance-attributes

    def __init__(
        self, parent: t.Optional[QtWidgets.QWidget] = None, *, plot_manager: PlotManager
    ) -> None:
        # pylint: disable = too-many-statements
        super().__init__(parent)
        # Set up internal attributes.
        self._machine = coi.Machine.NoMachine
        self._opt_builder = OptJobBuilder()
        self._current_opt_job: t.Optional[OptJob] = None
        self._plot_manager = plot_manager
        # Bind the job factories signals to the outside world.
        self._opt_builder.signals.objective_updated.connect(
            self._plot_manager.set_objective_curve_data
        )
        self._opt_builder.signals.actors_updated.connect(
            self._plot_manager.set_actors_curve_data
        )
        self._opt_builder.signals.constraints_updated.connect(
            self._plot_manager.set_constraints_curve_data
        )
        self._opt_builder.signals.optimisation_finished.connect(self._on_opt_finished)
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
        self.start_button = QtWidgets.QPushButton("Start")
        self.start_button.clicked.connect(self._on_start_clicked)
        self.stop_button = QtWidgets.QPushButton("Stop")
        self.stop_button.clicked.connect(self._on_stop_clicked)
        self.stop_button.setEnabled(False)
        self.reset_button = QtWidgets.QPushButton("Reset")
        self.reset_button.clicked.connect(self._on_reset_clicked)
        self.reset_button.setEnabled(False)
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
        run_control = QtWidgets.QHBoxLayout()
        run_control.setContentsMargins(0, 0, 0, 0)
        run_control.addWidget(self.start_button)
        run_control.addWidget(self.stop_button)
        run_control.addWidget(self.reset_button)
        layout.addLayout(run_control)
        # Fill all GUI elements, fire any events based on that.
        self.algo_combo.addItems(optimizers.ALL_OPTIMIZERS.keys())
        self.setMachine(self._machine)

    @contextlib.contextmanager
    def create_lsa_context(self, japc: "PyJapc") -> t.Iterator[None]:
        assert self._opt_builder.japc is None, "nested LSA context"
        self._opt_builder.japc = japc
        try:
            yield
        finally:
            self._opt_builder.unload_problem()
            self._opt_builder.japc = None

    def get_or_load_problem(self) -> t.Optional[optimizers.Optimizable]:
        if self._opt_builder.problem is not None:
            return self._opt_builder.problem
        please_wait_dialog = CreatingEnvDialog(self.window())
        please_wait_dialog.show()
        try:
            LOG.debug("initializing new problem: %s", self._opt_builder.problem_id)
            return self._opt_builder.make_problem()
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
        for env_spec in coi.registry.all():
            env_class = env_spec.entry_point
            env_machine = env_class.metadata.get("cern.machine", coi.Machine.NoMachine)
            is_optimizable = issubclass(
                env_class, (coi.SingleOptimizable, coi_funcs.FunctionOptimizable)
            )
            if machine == env_machine and is_optimizable:
                self.env_combo.addItem(env_spec.id)

    def _on_env_changed(self, name: str) -> None:
        self._opt_builder.problem_id = name
        self._clear_job()
        if name:
            env_spec = coi.spec(name)
            # TODO: This does not work well with wrappers.
            env_class = env_spec.entry_point
            is_configurable = issubclass(
                env_class, (coi.Configurable, coi_funcs.FunctionOptimizable)
            )
        else:
            is_configurable = False
        self.env_config_button.setEnabled(is_configurable)
        LOG.debug("configurable: %s", is_configurable)

    def _on_env_config_clicked(self) -> None:
        problem = self.get_or_load_problem()
        if problem is None:
            # Initialization failed, logs already made.
            return
        if not isinstance(
            problem.unwrapped, (coi.Configurable, coi_funcs.FunctionOptimizable)
        ):
            LOG.error("not configurable: %s", problem)
            return
        dialog = configuration.OptimizableDialog(
            problem,
            skeleton_points=self._opt_builder.skeleton_points,
            parent=self.window(),
        )
        dialog.config_applied.connect(
            lambda: self._set_skeleton_points(dialog.skeletonPoints())
        )
        dialog.open()

    def _set_skeleton_points(self, skeleton_points: np.ndarray) -> None:
        LOG.info("new skeleton points: %s", skeleton_points)
        self._opt_builder.skeleton_points = skeleton_points

    def _on_algo_changed(self, name: str) -> None:
        factory_class = optimizers.ALL_OPTIMIZERS[name]
        factory = factory_class()
        self._opt_builder.optimizer_factory = factory
        self.algo_config_button.setEnabled(isinstance(factory, coi.Configurable))

    def _on_algo_config_clicked(self) -> None:
        factory = self._opt_builder.optimizer_factory
        if not isinstance(factory, coi.Configurable):
            LOG.error("not configurable: %s", factory)
            return
        dialog = configuration.PureDialog(factory, self.window())
        dialog.open()

    def _on_start_clicked(self) -> None:
        # Let `self.get_or_load_problem()` to create the problem object
        # so that we get a please-wait dialog. `build_job()` would also
        # create it, but without visual feedback.
        problem = self.get_or_load_problem()
        if problem is None:
            return
        self._current_opt_job = self._opt_builder.build_job()
        assert self._current_opt_job is not None
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.reset_button.setEnabled(False)
        self._add_render_output(problem)
        threadpool = QtCore.QThreadPool.globalInstance()
        threadpool.start(self._current_opt_job)

    def _on_stop_clicked(self) -> None:
        if self._current_opt_job is None:
            LOG.error("there is nothing to stop")
            return
        LOG.debug("stopping ...")
        self.stop_button.setEnabled(False)
        self._current_opt_job.cancel()

    def _on_opt_finished(self) -> None:
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.reset_button.setEnabled(True)

    def _on_reset_clicked(self) -> None:
        if self._current_opt_job is None:
            LOG.error("cannot reset, no job has been run")
            return
        LOG.debug("resetting ...")
        self._current_opt_job.reset()
        problem = self._current_opt_job.problem
        if "matplotlib_figures" in problem.metadata.get("render.modes", []):
            problem.render(mode="matplotlib_figures")
            self._plot_manager.redraw_mpl_figures()

    def _clear_job(self) -> None:
        self._current_opt_job = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.reset_button.setEnabled(False)

    def _add_render_output(self, problem: coi.Problem) -> None:
        render_modes = problem.metadata.get("render.modes", [])
        if "matplotlib_figures" in render_modes:
            figures = problem.render(mode="matplotlib_figures")
            self._plot_manager.replace_mpl_figures(figures)
        else:
            self._plot_manager.clear_mpl_figures()
