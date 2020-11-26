"""The runner for all optimizers."""

import logging
import sys
import typing as t

import numpy as np
from PyQt5.QtCore import pyqtSignal, QObject, QRunnable, QThread, pyqtSlot

from .base_optimizer import BaseOptimizer

LOG = logging.getLogger(__name__)


class ConstraintsUpdateMessage:
    def __init__(self, *, values, lower_bound, upper_bound):
        self.values = values
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound


class OptimizationCancelled(Exception):
    """The user clicked the Stop button to cancel optimization."""


class OptimizerRunner(QRunnable):
    """Object that can drive optimizers in a background thread."""

    class Signals(QObject):
        """Collection of signals provided by the runner."""

        actors_updated = pyqtSignal(np.ndarray, np.ndarray)
        constraints_updated = pyqtSignal(np.ndarray, ConstraintsUpdateMessage)
        objective_updated = pyqtSignal(np.ndarray, np.ndarray)
        optimisation_finished = pyqtSignal(bool)

    signals = Signals()

    def __init__(self, optimizer: BaseOptimizer):
        super().__init__()
        self.optimizer = optimizer
        self.objectives_log = []
        self.actions_log = []
        self.constraints_log = []
        self._is_cancelled = False

    def cancel(self):
        """Cancel optimization at the next step.

        This function is typically called asynchronously. At the next
        optimization step, it will raise an exception in the cost
        function and thus hard-abort the optimization process.
        """
        self._is_cancelled = True

    def _env_callback(self, action):
        """The callback function provided to BaseOptimizer.solve()."""
        if self._is_cancelled:
            raise OptimizationCancelled()
        QThread.msleep(50)
        # Clip parameters into the valid range – COBYLA might otherwise go
        # out-of-bounds.
        env = self.optimizer.env
        action = np.clip(
            action,
            env.optimization_space.low,
            env.optimization_space.high,
        )
        self.actions_log.append(action.flatten())
        # Calculate loss function.
        loss = env.compute_single_objective(action.copy())
        assert np.ndim(loss) == 0, "non-scalar loss"
        self.objectives_log.append(loss)
        # Calculate constraints and mash all of them into a single array.
        self.constraints_log.append(
            all_into_flat_array(
                constraint.fun(action)
                for constraint in self.optimizer.wrapped_constraints
            )
        )
        # Log inputs and outputs.
        self._emit_all_signals()
        self._render_env()
        # Clear all constraint caches.
        for constraint in self.optimizer.wrapped_constraints:
            constraint.clear_cache()
        return loss

    def _emit_all_signals(self):
        iterations = np.arange(len(self.objectives_log))
        self.signals.objective_updated.emit(iterations, np.array(self.objectives_log))
        self.signals.actors_updated.emit(iterations, np.array(self.actions_log))
        self.signals.constraints_updated.emit(
            iterations,
            ConstraintsUpdateMessage(
                values=np.array(self.constraints_log),
                lower_bound=all_into_flat_array(
                    c.lb for c in self.optimizer.wrapped_constraints
                ),
                upper_bound=all_into_flat_array(
                    c.ub for c in self.optimizer.wrapped_constraints
                ),
            ),
        )

    def _render_env(self):
        env = self.optimizer.env
        if "matplotlib_figures" not in env.metadata.get("render.modes", []):
            return
        figures = env.render(mode="matplotlib_figures")
        for figure in figures:
            figure.canvas.draw_idle()

    @pyqtSlot()
    def run(self):
        # pylint: disable = bare-except
        try:
            optimum = self.optimizer.solve(self._env_callback)
            self._env_callback(optimum)
        except OptimizationCancelled:
            LOG.info("Manually cancelled optimization")
        except:
            sys.excepthook(*sys.exc_info())
            LOG.error("Aborted optimization due to the above exception")
        self.signals.optimisation_finished.emit(True)


def all_into_flat_array(values: t.Iterable[t.Union[float, np.ndarray]]) -> np.ndarray:
    """Dump arrays, scalars, etc. into a flat NumPy array."""
    return np.concatenate([np.asanyarray(value).flatten() for value in values])
