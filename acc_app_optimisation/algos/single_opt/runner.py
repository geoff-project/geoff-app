"""The runner for all optimizers."""

import logging
import traceback
import typing as t

import gym
import numpy as np
from PyQt5.QtCore import pyqtSignal, QObject, QRunnable, QThread, pyqtSlot
from cernml import coi, coi_funcs

from .base_optimizer import BaseOptimizer
from ...utils.bounded import BoundedArray

LOG = logging.getLogger(__name__)


class OptimizationCancelled(Exception):
    """The user clicked the Stop button to cancel optimization."""


class OptimizerRunner:
    """Long-lived object used to create and run optimization jobs.

    This class serves as an entry point to single-objective and function
    optimization. It:

    - keeps track of the data that has to be set up before optimization
      can start;
    - creates the runnable job objects that can be e.g. submitted to a
      thread pool; and
    - keeps a reference to the latest job.

    The last point allows e.g. undoing and cancelling optimization.
    """

    class Signals(QObject):
        """Collection of signals provided by the runner."""

        actors_updated = pyqtSignal(np.ndarray, np.ndarray)
        constraints_updated = pyqtSignal(np.ndarray, BoundedArray)
        objective_updated = pyqtSignal(np.ndarray, np.ndarray)
        optimisation_finished = pyqtSignal(bool)

    def __init__(self) -> None:
        self._optimizer_class: t.Optional[t.Type[BaseOptimizer]] = None
        self._optimizer: t.Optional[BaseOptimizer] = None
        self._problem: t.Optional[coi.Problem] = None
        self.last_job: t.Optional["AbstractJob"] = None
        self._skeleton_points: t.Optional[np.ndarray] = None
        self.signals = self.Signals()

    @property
    def skeleton_points(self) -> t.Optional[np.ndarray]:
        """The skeleton points used by `coi_funcs.FunctionOptimizable`."""
        return self._skeleton_points

    def set_skeleton_points(self, points: t.Optional[np.ndarray]) -> None:
        """Pass a new set of skeletons points to the runner."""
        self._skeleton_points = points

    @property
    def problem(self) -> t.Optional[coi.Problem]:
        """The optimization problem used for the next optimization."""
        return self._problem

    def set_problem(self, problem: t.Optional[coi.Problem]) -> None:
        """Change the optimization problem used for the next optimization."""
        old_spec = getattr(self._problem, "spec", None)
        if problem is None or problem.spec is not old_spec:
            self._skeleton_points = None
        self._problem = problem
        self._update_optimizer()

    @property
    def optimizer(self) -> t.Optional[BaseOptimizer]:
        """The optimizer used for the next optimization."""
        return self._optimizer

    def set_optimizer_class(self, opt_class: t.Type[BaseOptimizer]) -> None:
        """Change the optimizer and optimization problem.

        If the optimization problem changes, this clears out the last
        completed job. If that job is still running, it is cancelled
        first.
        """
        if opt_class is self._optimizer_class:
            return
        self._optimizer_class = opt_class
        self._update_optimizer()

    def _update_optimizer(self) -> None:
        if self._optimizer_class is not None and self._problem is not None:
            self._optimizer = self._optimizer_class(self._problem)
        else:
            self._optimizer = None

    def is_ready_to_run(self) -> bool:
        """Return True if everything is set up to start a job."""
        if not self.optimizer:
            return False
        env = self.optimizer.env
        if isinstance(env, coi.SingleOptimizable):
            return True
        if isinstance(env, coi_funcs.FunctionOptimizable):
            points = self.skeleton_points
            return points is not None and np.size(points)
        raise TypeError(f"Cannot optimize: {env}")

    def create_job(self) -> "AbstractJob":
        """Create a new job ready to be submitted to a threadpool.

        If an old job exists, it is cancelled first.
        """
        if self.optimizer is None:
            raise ValueError("no optimizer selected")
        env = self.problem
        if isinstance(env, coi.SingleOptimizable):
            job = SingleOptJob(self)
        elif isinstance(env, coi_funcs.FunctionOptimizable):
            job = FunctionOptJob(self)
        else:
            raise TypeError(f"Cannot optimize: {env}")
        if self.last_job:
            self.last_job.cancel()
        self.last_job = job
        return job


class AbstractJob(QRunnable):
    """Interface of the jobs created by the `OptimizerRunner`.

    Depending on the optimization problem, the `OptimizerRunner` might
    start different kinds of job. However, all jobs satisfy this
    interface:

    - they can be submitted to a thread pool as a `QRunnable`;
    - they can be cancelled;
    - theyr record the initial state of the optimization problem and
      allow resetting it.

    Most jobs will implement cancellation as a *request*: Calling
    `cancel()` will merely set a flag that is periodically checked by
    the job. This is the only way to guarantee a clean shutdown in a
    multithreaded environment.

    In most cases, "reset" merely means that the (possibly stateful)
    objective function is evaluated using the initial parameters.
    """

    def reset(self) -> None:
        """Evaluate the environment at x_0."""
        raise NotImplementedError()

    def cancel(self) -> None:
        """Cancel optimization at the next step.

        This function is typically called asynchronously. At the next
        optimization step, it will raise an exception in the cost
        function and thus hard-abort the optimization process.
        """
        raise NotImplementedError()


class _SingleAndFunctionOptJobBase(AbstractJob):
    """Common logic of `SingleOptJob` and `FunctionOptJob`."""

    def __init__(self, parent: OptimizerRunner) -> None:
        super().__init__()
        self.optimizer = parent.optimizer
        self.signals = parent.signals
        self.objectives_log = []
        self.actions_log = []
        self.constraints_log = []
        self._is_cancelled = False

    def get_optimization_space(self) -> gym.spaces.Box:
        """Extract the optimization space from the problem."""
        raise NotImplementedError()

    def compute_loss(self, normalized_action: np.ndarray) -> float:
        """Extract the optimization space from the problem."""
        raise NotImplementedError()

    def run_optimization(self) -> None:
        """The implementation of the optimization procedure."""
        raise NotImplementedError()

    def cancel(self):
        """Cancel optimization at the next step.

        This function is typically called asynchronously. At the next
        optimization step, it will raise an exception in the cost
        function and thus hard-abort the optimization process.
        """
        self._is_cancelled = True

    @pyqtSlot()
    def run(self):
        """Implementation of `QRunnable.run()`."""
        # pylint: disable = bare-except
        try:
            self.run_optimization()
        except OptimizationCancelled:
            LOG.info("Manually cancelled optimization")
        except:
            LOG.error(traceback.format_exc())
            LOG.error("Aborted optimization due to the above exception")
        self.signals.optimisation_finished.emit(True)

    def _env_callback(self, action: np.ndarray) -> float:
        """The callback function provided to BaseOptimizer.solve()."""
        if self._is_cancelled:
            raise OptimizationCancelled()
        # Yield at least once per optimization step. This releases
        # Python's Global Interpreter Lock (GIL) and gives the main
        # thread a chance to process GUI events.
        QThread.yieldCurrentThread()
        # Clip parameters into the valid range – COBYLA might otherwise go
        # out-of-bounds.
        opt_space = self.get_optimization_space()
        action = np.clip(action, opt_space.low, opt_space.high)
        self.actions_log.append(action.flatten())
        # Calculate loss function.
        loss = self.compute_loss(action.copy())
        assert np.ndim(loss) == 0, "non-scalar loss"
        self.objectives_log.append(loss)
        # Calculate constraints and mash all of them into a single array.
        if self.optimizer.wrapped_constraints:
            self.constraints_log.append(
                all_into_flat_array(
                    constraint.fun(action)
                    for constraint in self.optimizer.wrapped_constraints
                )
            )
            for constraint in self.optimizer.wrapped_constraints:
                constraint.clear_cache()
        # Log inputs and outputs.
        self._emit_all_signals()
        self._render_env()
        # Clear all constraint caches.
        return loss

    def _emit_all_signals(self):
        iterations = np.arange(len(self.objectives_log))
        self.signals.objective_updated.emit(iterations, np.array(self.objectives_log))
        self.signals.actors_updated.emit(iterations, np.array(self.actions_log))
        constraints = self.optimizer.wrapped_constraints
        if constraints:
            self.signals.constraints_updated.emit(
                iterations,
                BoundedArray(
                    values=np.array(self.constraints_log),
                    lower=all_into_flat_array(c.lb for c in constraints),
                    upper=all_into_flat_array(c.ub for c in constraints),
                ),
            )

    def _render_env(self):
        env = self.optimizer.env
        if "matplotlib_figures" not in env.metadata.get("render.modes", []):
            return
        figures = env.render(mode="matplotlib_figures")
        # `draw()` refreshes the figures immediately on this thread. Do
        # not use `draw_idle()`: it postpones drawing until the next
        # time the (main thread) event loop runs. This leads to a race
        # condition between the main thread drawing the figures and this
        # thread modifying them.
        for figure in figures:
            QThread.yieldCurrentThread()
            figure.canvas.draw()


class SingleOptJob(_SingleAndFunctionOptJobBase):
    """Job that optimizes `SingleOptimizable` problems."""

    def __init__(self, parent: OptimizerRunner) -> None:
        super().__init__(parent)
        self.env = t.cast(coi.SingleOptimizable, self.optimizer.env)
        self.x_0 = self.env.get_initial_params()

    def reset(self) -> None:
        # TODO: Do we need to normalize x_0 here?
        self.env.compute_single_objective(self.x_0)

    def get_optimization_space(self) -> gym.spaces.Box:
        return self.env.optimization_space

    def compute_loss(self, normalized_action: np.ndarray) -> float:
        return self.env.compute_single_objective(normalized_action)

    def run_optimization(self) -> None:
        optimum = self.optimizer.solve(self._env_callback, self.x_0.copy())
        self._env_callback(optimum)


class FunctionOptJob(_SingleAndFunctionOptJobBase):
    """Job that optimizes `FunctionOptimizable` problems."""

    def __init__(self, parent: OptimizerRunner) -> None:
        super().__init__(parent)
        self.env = t.cast(coi_funcs.FunctionOptimizable, self.optimizer.env)
        self.skeleton_points = parent.skeleton_points
        self.all_x_0 = [
            self.env.get_initial_params(point) for point in self.skeleton_points
        ]
        self._current_point: t.Optional[float] = None

    def reset(self) -> None:
        # TODO: Do we need to normalize x_0 here?
        for point, x_0 in zip(self.skeleton_points, self.all_x_0):
            self.env.compute_function_objective(point, x_0)

    def get_optimization_space(self) -> gym.spaces.Box:
        assert self._current_point is not None
        return self.env.get_optimization_space(self._current_point)

    def compute_loss(self, normalized_action: np.ndarray) -> float:
        assert self._current_point is not None
        return self.env.compute_function_objective(
            self._current_point, normalized_action
        )

    def run_optimization(self) -> None:
        for point, x_0 in zip(self.skeleton_points, self.all_x_0):
            self._current_point = point
            optimum = self.optimizer.solve(self._env_callback, x_0.copy())
            self._env_callback(optimum)


def all_into_flat_array(values: t.Iterable[t.Union[float, np.ndarray]]) -> np.ndarray:
    """Dump arrays, scalars, etc. into a flat NumPy array."""
    flat_arrays = [np.ravel(np.asanyarray(value)) for value in values]
    return np.concatenate(flat_arrays) if flat_arrays else np.array([])
