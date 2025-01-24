# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

import traceback
import typing as t
from dataclasses import dataclass
from logging import getLogger

import cernml.optimizers as opt
import gymnasium as gym
import numpy as np
from cernml.coi import FunctionOptimizable, SingleOptimizable, cancellation
from cernml.mpl_utils import iter_matplotlib_figures
from PyQt5 import QtCore

from ...envs import Metadata
from ...utils.bounded import BoundedArray
from ...utils.typecheck import AnyOptimizable
from ..base import BenignCancelledError, Job, catching_exceptions
from . import constraints
from .skeleton_points import SkeletonPoints

LOG = getLogger(__name__)


class BadInitialPoint(Exception):
    """The initial point has not the correct shape or type."""


@dataclass(frozen=True)
class PreOptimizationMetadata:
    """Message object that provides information just before optimization.

    Attributes:
        problem_id: The registered name of the optimization problem that
            is being optimized.
        objective_name: The physical meaning of the objective function,
            e.g. a device name.
        param_names: The physical meaning of each parameter, e.g. a
            device name.
        constraint_names: The physical meaning of each constraint, e.g.
            a device name.
        max_function_evaluations: A parameter configured on the
            optimization algorithm that limits the number of function
            evaluations. `None` if there is no limit or no limit could
            be found (e.g. because GeOFF does not know the parameter's
            name).
    """

    problem_id: str
    objective_name: str
    param_names: t.Tuple[str, ...]
    constraint_names: t.Tuple[str, ...]
    max_function_evaluations: t.Optional[int]


@dataclass(frozen=True)
class PreStepMetadata:
    """Message object that provides info right before a step happens.

    Attributes:
        action: The next action sent to the optimization problem.
        final_step: False during optimization. True for the final
            evaluation of :math:`f(x^*)` after optimization.
    """

    action: np.ndarray
    final_step: bool


class Signals(QtCore.QObject):
    """Signals emitted by `OptJob`.

    Attributes:
        new_optimisation_started:
            Emitted before optimization starts, but after *x₀* has been
            extracted via `AnyOptimizable.get_initial_params()`.
        step_started:
            Emitted right before evaluation of
            `SingleOptimizable.compute_single_objective()` and
            `FunctionOptimizable.compute_function_objective()`.
        new_skeleton_point_selected:
            Emitted whenever `FunctionOptimizableJob` switches to a new
            skeleton point. This happens while extracting *x₀*, during
            optimization and while resetting.
        actors_updated:
            Emitted at the end of an optimization step. First parameter
            is an array of shape :math:`(N,)` with all iteration indices
            as X coordinates, second parameter is a 2D array of shape
            :math:`(N, A)` with the history of all actions send to the
            optimization problem.
        constraints_updated:
            Emitted at the end of an optimization step, together with
            *actors_updated*, but only if the optimization problem
            defines any constraints. Contains the bounds and current
            values of all constraints in a similar format to
            *actors_updated*, but with a `BoundedArray` wrapping around
            the Y coordinates.
        objective_updated:
            Emitted at the end of an optimization step, together with
            *actors_updated*. Contains the history of the objective
            function values. Similar format to *actors_updated*, but the
            second parameter is a 1D array of shape :math:`(N,)`.
        optimisation_finished:
            Emitted at the end of optimization. The Boolean argument is
            True if optimization ran until completion, False if it was
            cancelled by the user.
        optimisation_failed:
            Emitted after optimization ended irregularly through an
            exception *other than*
            `cernml.coi.cancellation.CancelledError`.
    """

    new_optimisation_started = QtCore.pyqtSignal(PreOptimizationMetadata)
    step_started = QtCore.pyqtSignal(PreStepMetadata)
    new_skeleton_point_selected = QtCore.pyqtSignal(float)
    objective_updated = QtCore.pyqtSignal(np.ndarray, np.ndarray)
    actors_updated = QtCore.pyqtSignal(np.ndarray, np.ndarray)
    constraints_updated = QtCore.pyqtSignal(np.ndarray, BoundedArray)
    optimisation_finished = QtCore.pyqtSignal(bool)
    optimisation_failed = QtCore.pyqtSignal(traceback.TracebackException)


class OptJob(Job):
    """Common logic of all optimizations.

    This is a code-sharing base class of `SingleOptimizableJob` and
    `FunctionOptimizableJob`.
    """

    wrapped_constraints: t.List[constraints.CachedNonlinearConstraint]
    problem: AnyOptimizable

    def __init__(
        self,
        *,
        token_source: cancellation.TokenSource,
        signals: Signals,
        problem: AnyOptimizable,
        optimizer: opt.Optimizer,
    ) -> None:
        super().__init__(token_source)
        self.optimizer = optimizer
        self.problem = problem
        self.wrapped_constraints = [
            constraints.CachedNonlinearConstraint.from_any_constraint(c)
            for c in problem.constraints
        ]
        self._signals = signals
        self.objectives_log: t.List[float] = []
        self.actions_log: t.List[np.ndarray] = []
        self.constraints_log: t.List[np.ndarray] = []

    @property
    def optimizer_id(self) -> str:
        """The name of the optimization algorithm."""
        optimizer = self.optimizer
        spec: t.Optional[opt.OptimizerSpec] = getattr(optimizer, "spec", None)
        if spec:
            return spec.name
        return _get_any_obj_repr(optimizer)

    @property
    def problem_id(self) -> str:
        """The name of the optimization problem."""
        problem = self.problem.unwrapped
        spec: t.Optional[gym.envs.registration.EnvSpec] = getattr(problem, "spec", None)
        if spec:
            return spec.id
        return _get_any_obj_repr(problem)

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

    def get_param_names(self) -> t.Tuple[str, ...]:
        raise NotImplementedError()

    def get_constraint_names(self) -> t.Tuple[str, ...]:
        raise NotImplementedError()

    def get_objective_name(self) -> str:
        raise NotImplementedError()

    def format_reset_point(self) -> str:
        """Format the point to which reset() will go as a string."""
        raise NotImplementedError()

    @QtCore.pyqtSlot()
    def run(self) -> None:
        """Implementation of `QRunnable.run()`."""
        with catching_exceptions(
            "optimization",
            LOG,
            token_source=self._token_source,
            on_success=lambda: self._signals.optimisation_finished.emit(True),
            on_cancel=lambda: self._signals.optimisation_finished.emit(False),
            on_exception=self._signals.optimisation_failed.emit,
        ):
            self.run_optimization()

    def _env_callback(self, action: np.ndarray, final_step: bool = False) -> float:
        """The callback function provided to BaseOptimizer.solve().

        Args:
            action: The next evaluation point suggested by the
                optimization algorithm.
            final_step: Usually False. Subclasses should pass True for
                the final evaluation :math:`f(x^*)`. This is used to
                emit the `~Signals.step_started` signal.
        """
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
        self._signals.step_started.emit(PreStepMetadata(action.copy(), final_step))
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
        self.actions_log.append(action.flatten())
        self.objectives_log.append(loss)
        if self.wrapped_constraints:
            self.constraints_log.append(constraints_values)
        self._emit_all_signals()
        self._render_env()
        # Clear all constraint caches.
        return loss

    def _emit_all_signals(self) -> None:
        iterations = np.arange(len(self.objectives_log))
        self._signals.objective_updated.emit(iterations, np.array(self.objectives_log))
        self._signals.actors_updated.emit(iterations, np.array(self.actions_log))
        if self.wrapped_constraints:
            self._signals.constraints_updated.emit(
                iterations,
                BoundedArray(
                    values=np.array(self.constraints_log),
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
        optimizer: opt.Optimizer,
    ) -> None:
        super().__init__(
            token_source=token_source,
            signals=signals,
            problem=problem,
            optimizer=optimizer,
        )
        unvalidated_x0 = self.problem.get_initial_params()
        try:
            self.x_0 = validate_x0(unvalidated_x0)
        except BadInitialPoint:
            LOG.warning("x0=%r", unvalidated_x0)
            raise

    def reset(self) -> None:
        with catching_exceptions(
            "reset",
            LOG,
            token_source=self._token_source,
            on_success=lambda: self._signals.optimisation_finished.emit(True),
            on_cancel=lambda: self._signals.optimisation_finished.emit(False),
            on_exception=self._signals.optimisation_failed.emit,
        ):
            LOG.info("start reset of %s using %s", self.problem_id, self.optimizer_id)
            self._env_callback(self.x_0)

    def format_reset_point(self) -> str:
        return "\n".join(map("{}:\t{}".format, self.get_param_names(), self.x_0))

    def get_optimization_space(self) -> gym.spaces.Box:
        return self.problem.optimization_space

    def compute_loss(self, normalized_action: np.ndarray) -> float:
        return self.problem.compute_single_objective(normalized_action)

    def run_optimization(self) -> None:
        LOG.info(
            "start optimization of %s using %s", self.problem_id, self.optimizer_id
        )
        self._signals.new_optimisation_started.emit(
            PreOptimizationMetadata(
                problem_id=self.problem_id,
                objective_name=self.get_objective_name(),
                param_names=self.get_param_names(),
                constraint_names=self.get_constraint_names(),
                max_function_evaluations=_guess_maxfevs(self.optimizer),
            )
        )
        opt_space = self.problem.optimization_space
        solve = self.optimizer.make_solve_func(
            (opt_space.low, opt_space.high), self.wrapped_constraints
        )
        optimum = solve(self._env_callback, self.x_0.copy())
        self._env_callback(optimum.x, final_step=True)

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

    def get_objective_name(self) -> str:
        return str(self.problem.objective_name) or "Objective function"


class FunctionOptimizableJob(OptJob):
    """Job that optimizes `FunctionOptimizable` problems."""

    problem: FunctionOptimizable

    def __init__(
        self,
        *,
        token_source: cancellation.TokenSource,
        signals: Signals,
        problem: FunctionOptimizable,
        optimizer: opt.Optimizer,
        skeleton_points: SkeletonPoints,
    ) -> None:
        super().__init__(
            token_source=token_source,
            signals=signals,
            problem=problem,
            optimizer=optimizer,
        )
        self.skeleton_points = skeleton_points
        self.all_x_0 = []
        for point in self.skeleton_points:
            self._signals.new_skeleton_point_selected.emit(point)
            unvalidated_x0 = problem.get_initial_params(point)
            try:
                self.all_x_0.append(validate_x0(unvalidated_x0))
            except BadInitialPoint:
                LOG.warning("t=%g ms, x0=%r", point, unvalidated_x0)
                raise
        self._current_point: t.Optional[float] = None

    def reset(self) -> None:
        with catching_exceptions(
            "reset",
            LOG,
            token_source=self._token_source,
            on_success=lambda: self._signals.optimisation_finished.emit(True),
            on_cancel=lambda: self._signals.optimisation_finished.emit(False),
            on_exception=self._signals.optimisation_failed.emit,
        ):
            LOG.info("start reset of %s using %s", self.problem_id, self.optimizer_id)
            # TODO: Only reset up to and including the current point.
            token = self._token_source.token
            for point, x_0 in zip(self.skeleton_points, self.all_x_0):
                if token.cancellation_requested:
                    token.complete_cancellation()
                    raise BenignCancelledError()
                LOG.info("next skeleton point: %g", point)
                LOG.info("x0 = %s", x_0)
                self._signals.new_skeleton_point_selected.emit(point)
                self._current_point = point
                self._env_callback(x_0)

    def format_reset_point(self) -> str:
        param_names = self.get_param_names()
        hline = 40 * "-"

        def _format_single_point(skeleton_point: float, x_0: np.ndarray) -> str:
            lines = [hline, f"At t={skeleton_point}", hline]
            lines.extend(map("{}:\t{}".format, param_names, x_0))
            return "\n".join(lines)

        return "\n\n".join(
            map(_format_single_point, self.skeleton_points, self.all_x_0)
        )

    def get_optimization_space(self) -> gym.spaces.Box:
        assert self._current_point is not None
        return self.problem.get_optimization_space(self._current_point)

    def compute_loss(self, normalized_action: np.ndarray) -> float:
        assert self._current_point is not None
        return self.problem.compute_function_objective(
            self._current_point, normalized_action
        )

    def run_optimization(self) -> None:
        LOG.info(
            "start optimization of %s using %s", self.problem_id, self.optimizer_id
        )
        # TODO: Right now, we create one plot for all optimizations.
        # This is fundamentally incompatible with our promise to allow
        # different numers of parameters for each skeleton point. We
        # will have to change this eventually.
        self._signals.new_optimisation_started.emit(
            PreOptimizationMetadata(
                problem_id=self.problem_id,
                objective_name=self.get_objective_name(),
                param_names=self.get_param_names(),
                constraint_names=self.get_constraint_names(),
                max_function_evaluations=_guess_maxfevs(self.optimizer),
            )
        )
        for point, x_0 in zip(self.skeleton_points, self.all_x_0):
            if self._token_source.token.cancellation_requested:
                raise BenignCancelledError()
            LOG.info("next skeleton point: %g", point)
            LOG.info("x0 = %s", x_0)
            self._signals.new_skeleton_point_selected.emit(point)
            self._current_point = point
            op_space = self.get_optimization_space()
            solve = self.optimizer.make_solve_func(
                (op_space.low, op_space.high),
                self.wrapped_constraints,
            )
            optimum = solve(self._env_callback, x_0.copy())
            self._env_callback(optimum.x, final_step=True)

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

    def get_objective_name(self) -> str:
        return str(self.problem.get_objective_function_name()) or "Objective function"


def validate_x0(array: np.ndarray) -> np.ndarray:
    """Raise BadInitialPoint if array is not a flat floating-point array."""
    array = np.asanyarray(array)
    if array.ndim != 1:
        raise BadInitialPoint(
            f"bad shape: expected a 1-D array, got shape={array.shape}"
        )
    # We exceptionally also accept unsigned ("u") and signed ("i")
    # integers, but only because most optimizers cast them to float
    # without issues. The one thing this guards against is
    # `dtype('object')`, which we can occasionally get if PyJapc returns
    # something weird.
    if array.dtype.kind not in "uif":
        raise BadInitialPoint(
            f"bad type: expected a float array, got dtype={array.dtype}"
        )
    return array


def all_into_flat_array(values: t.Iterable[t.Union[float, np.ndarray]]) -> np.ndarray:
    """Dump arrays, scalars, etc. into a flat NumPy array."""
    flat_arrays = [np.ravel(np.asanyarray(value)) for value in values]
    return np.concatenate(flat_arrays) if flat_arrays else np.array([])


def _get_any_obj_repr(obj: t.Any) -> str:
    class_ = type(obj)
    name: t.Optional[str] = getattr(obj, "__qualname__", None)
    name = name or getattr(class_, "__name__", None)
    if not name:
        return repr(obj)
    module: str = getattr(class_, "__module__", "<unknown module>")
    return ".".join((module, name))


def _guess_maxfevs(optimizer: opt.Optimizer) -> t.Optional[int]:
    for attr in ["maxfun", "max_calls", "n_calls", "total_timesteps"]:
        maxfevs = getattr(optimizer, attr, None)
        if maxfevs is not None:
            try:
                return int(maxfevs)
            except TypeError:
                pass
    return None
