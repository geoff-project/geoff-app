import typing as t
from dataclasses import dataclass
from logging import getLogger

import gym
import numpy as np
import scipy.optimize
from cernml.coi import FunctionOptimizable, SingleOptimizable, cancellation
from cernml.mpl_utils import iter_matplotlib_figures
from PyQt5 import QtCore

from ...envs import Metadata
from ...utils.bounded import BoundedArray
from ..base import Job
from . import constraints, optimizers

LOG = getLogger(__name__)


class BenignCancelledError(cancellation.CancelledError):
    """Cancellation error that we raise, not the :class:`SingleOptimizable`."""


@dataclass(frozen=True)
class PreOptimizationMetadata:
    """Message object that provides information just before optimization.

    Attributes:
        objective_name: The physical meaning of the objective function,
            e.g. a device name.
        param_names: The physical meaning of each parameter, e.g. a
            device name.
        constraint_names: The physical meaning of each constraint, e.g.
            a device name.
    """

    objective_name: str
    param_names: t.Tuple[str, ...]
    constraint_names: t.Tuple[str, ...]


class Signals(QtCore.QObject):
    new_optimisation_started = QtCore.pyqtSignal(PreOptimizationMetadata)
    actors_updated = QtCore.pyqtSignal(np.ndarray, np.ndarray)
    constraints_updated = QtCore.pyqtSignal(np.ndarray, BoundedArray)
    objective_updated = QtCore.pyqtSignal(np.ndarray, np.ndarray)
    optimisation_finished = QtCore.pyqtSignal(bool)


class OptJob(Job):
    """Common logic of all optimizations.

    This is a code-sharing base class of `SingleOptimizableJob` and
    `FunctionOptimizableJob`.
    """

    wrapped_constraints: t.List[constraints.CachedNonlinearConstraint]
    problem: optimizers.Optimizable

    def __init__(
        self,
        *,
        token_source: cancellation.TokenSource,
        signals: Signals,
        problem: optimizers.Optimizable,
    ) -> None:
        super().__init__(token_source)
        self.problem = problem
        self.wrapped_constraints = [
            constraints.CachedNonlinearConstraint.from_any_constraint(c)
            for c in problem.constraints
        ]
        self._signals = signals
        self._objectives_log: t.List[float] = []
        self._actions_log: t.List[np.ndarray] = []
        self._constraints_log: t.List[np.ndarray] = []

    def get_optimization_space(self) -> gym.spaces.Box:
        """Extract the optimization space from the problem."""
        raise NotImplementedError()

    def compute_loss(self, normalized_action: np.ndarray) -> float:
        """Extract the optimization space from the problem."""
        raise NotImplementedError()

    def run_optimization(self) -> None:
        """The implementation of the optimization procedure."""
        raise NotImplementedError()

    def reset(self) -> None:
        """Evaluate the problem at x_0."""
        raise NotImplementedError()

    @QtCore.pyqtSlot()
    def run(self) -> None:
        """Implementation of `QRunnable.run()`."""
        # pylint: disable = bare-except
        try:
            self.run_optimization()
        except cancellation.CancelledError as exc:
            if isinstance(exc, BenignCancelledError):
                self._token_source.token.complete_cancellation()
            LOG.info("cancelled optimization")
        except:
            LOG.error("aborted optimization", exc_info=True)
        else:
            LOG.info("finished optimization")
        if self._token_source.can_reset_cancellation:
            self._token_source.reset_cancellation()
        self._signals.optimisation_finished.emit(True)

    def _env_callback(self, action: np.ndarray) -> float:
        """The callback function provided to BaseOptimizer.solve()."""
        if self._token_source.token.cancellation_requested:
            raise BenignCancelledError()
        # Yield at least once per optimization step. This releases
        # Python's Global Interpreter Lock (GIL) and gives the main
        # thread a chance to process GUI events.
        QtCore.QThread.yieldCurrentThread()
        # Clip parameters into the valid range – COBYLA might otherwise go
        # out-of-bounds.
        opt_space = self.get_optimization_space()
        action = np.clip(action, opt_space.low, opt_space.high)
        # Calculate loss function.
        loss = self.compute_loss(action.copy())
        assert np.ndim(loss) == 0, "non-scalar loss"
        if self.wrapped_constraints:
            constraints_values = all_into_flat_array(
                constraint.fun(action) for constraint in self.wrapped_constraints
            )
            for constraint in self.wrapped_constraints:
                constraint.clear_cache()
        # Log inputs and outputs. Only adjust the logs after all user
        # functions have been called. Otherwise, we risk unequal lengths
        # between the log arrays.
        self._actions_log.append(action.flatten())
        self._objectives_log.append(loss)
        if self.wrapped_constraints:
            self._constraints_log.append(constraints_values)
        self._emit_all_signals()
        self._render_env()
        # Clear all constraint caches.
        return loss

    def _emit_all_signals(self) -> None:
        iterations = np.arange(len(self._objectives_log))
        self._signals.objective_updated.emit(iterations, np.array(self._objectives_log))
        self._signals.actors_updated.emit(iterations, np.array(self._actions_log))
        if self.wrapped_constraints:
            self._signals.constraints_updated.emit(
                iterations,
                BoundedArray(
                    values=np.array(self._constraints_log),
                    lower=all_into_flat_array(c.lb for c in self.wrapped_constraints),
                    upper=all_into_flat_array(c.ub for c in self.wrapped_constraints),
                ),
            )

    def _render_env(self) -> None:
        if "matplotlib_figures" not in Metadata(self.problem).render_modes:
            return
        figures = self.problem.render(mode="matplotlib_figures")
        # `draw()` refreshes the figures immediately on this thread. Do
        # not use `draw_idle()`: it postpones drawing until the next
        # time the (main thread) event loop runs. This leads to a race
        # condition between the main thread drawing the figures and this
        # thread modifying them.
        for _, figure in iter_matplotlib_figures(figures):
            QtCore.QThread.yieldCurrentThread()
            figure.canvas.draw()


class SingleOptimizableJob(OptJob):
    """Job that optimizes `SingleOptimizable` problems."""

    problem: SingleOptimizable

    def __init__(
        self,
        *,
        token_source: cancellation.TokenSource,
        signals: Signals,
        problem: SingleOptimizable,
        optimizer_factory: optimizers.OptimizerFactory,
    ) -> None:
        super().__init__(token_source=token_source, signals=signals, problem=problem)
        self.x_0 = self.problem.get_initial_params()
        self._solve = optimizer_factory.make_solve_func(
            scipy.optimize.Bounds(
                problem.optimization_space.low, problem.optimization_space.high
            ),
            self.wrapped_constraints,
        )

    def reset(self) -> None:
        self._env_callback(self.x_0)

    def get_optimization_space(self) -> gym.spaces.Box:
        return self.problem.optimization_space

    def compute_loss(self, normalized_action: np.ndarray) -> float:
        return self.problem.compute_single_objective(normalized_action)

    def run_optimization(self) -> None:
        self._signals.new_optimisation_started.emit(
            PreOptimizationMetadata(
                objective_name=str(self.problem.objective_name),
                param_names=self.get_param_names(),
                constraint_names=self.get_constraint_names(),
            )
        )
        optimum = self._solve(self._env_callback, self.x_0.copy())
        self._env_callback(optimum)

    def get_param_names(self) -> t.Tuple[str, ...]:
        """Read the problem's parameter names or supply defaults.

        Whereas ``problem.param_names`` may be an empty sequence, the
        tuple returned by this function will always have as many
        elements as the first result of` `get_initial_params()``.
        """
        indices = range(1, 1 + len(self.x_0))
        return tuple(self.problem.param_names) or tuple(f"Actor {i}" for i in indices)

    def get_constraint_names(self) -> t.Tuple[str, ...]:
        """Read the problem's constraint names or supply defaults.

        Whereas ``problem.constraint_names`` may be an empty sequence,
        the tuple returned by this function will always have as many
        elements as ``problem.constraints``.
        """
        indices = range(1, 1 + len(self.problem.constraints))
        return tuple(self.problem.constraint_names) or tuple(
            f"Constraint {i}" for i in indices
        )


class FunctionOptimizableJob(OptJob):
    """Job that optimizes `FunctionOptimizable` problems."""

    problem: FunctionOptimizable

    def __init__(
        self,
        *,
        token_source: cancellation.TokenSource,
        signals: Signals,
        problem: FunctionOptimizable,
        optimizer_factory: optimizers.OptimizerFactory,
        skeleton_points: t.Iterable[float],
    ) -> None:
        super().__init__(token_source=token_source, signals=signals, problem=problem)
        self.skeleton_points = tuple(skeleton_points)
        self.all_x_0 = [
            problem.get_initial_params(point) for point in self.skeleton_points
        ]
        self._current_point: t.Optional[float] = None
        self._factory = optimizer_factory

    def reset(self) -> None:
        # TODO: Only reset up to and including the current point.
        for point, x_0 in zip(self.skeleton_points, self.all_x_0):
            self.problem.compute_function_objective(point, x_0)
            self._current_point = point
            self._env_callback(x_0)

    def get_optimization_space(self) -> gym.spaces.Box:
        assert self._current_point is not None
        return self.problem.get_optimization_space(self._current_point)

    def compute_loss(self, normalized_action: np.ndarray) -> float:
        assert self._current_point is not None
        return self.problem.compute_function_objective(
            self._current_point, normalized_action
        )

    def run_optimization(self) -> None:
        # TODO: Right now, we create one plot for all optimizations.
        # This is fundamentally incompatible with our promise to allow
        # different numers of parameters for each skeleton point. We
        # will have to change this eventually.
        self._signals.new_optimisation_started.emit(
            PreOptimizationMetadata(
                objective_name=str(self.problem.get_objective_function_name()),
                param_names=self.get_param_names(),
                constraint_names=self.get_constraint_names(),
            )
        )
        for point, x_0 in zip(self.skeleton_points, self.all_x_0):
            if self._token_source.token.cancellation_requested:
                raise BenignCancelledError()
            self._current_point = point
            op_space = self.get_optimization_space()
            solve = self._factory.make_solve_func(
                scipy.optimize.Bounds(op_space.low, op_space.high),
                self.wrapped_constraints,
            )
            optimum = solve(self._env_callback, x_0.copy())
            self._env_callback(optimum)

    def get_param_names(self) -> t.Tuple[str, ...]:
        """Read the problem's parameter names or supply defaults.

        Whereas ``problem.get_param_function_names()`` may return an
        empty sequence, the tuple returned by this function will always
        have as many elements as the first result of`
        `get_initial_params()``.
        """
        indices = range(1, 1 + len(self.all_x_0[0]))
        return tuple(self.problem.get_param_function_names()) or tuple(
            f"Actor {i}" for i in indices
        )

    def get_constraint_names(self) -> t.Tuple[str, ...]:
        """Read the problem's constraint names or supply defaults.

        Whereas ``problem.constraint_names`` may be an empty sequence,
        the tuple returned by this function will always have as many
        elements as ``problem.constraints``.
        """
        indices = range(1, 1 + len(self.problem.constraints))
        return tuple(getattr(self.problem, "constraint_names", ())) or tuple(
            f"Constraint {i}" for i in indices
        )


def all_into_flat_array(values: t.Iterable[t.Union[float, np.ndarray]]) -> np.ndarray:
    """Dump arrays, scalars, etc. into a flat NumPy array."""
    flat_arrays = [np.ravel(np.asanyarray(value)) for value in values]
    return np.concatenate(flat_arrays) if flat_arrays else np.array([])
