"""The runner for all optimizers."""

import logging
import sys
import typing as t

import numpy as np
from PyQt5.QtCore import pyqtSignal, QObject, QRunnable, QThread, pyqtSlot

from .base_optimizer import BaseOptimizer
from ...utils.bounded import BoundedArray

LOG = logging.getLogger(__name__)


class OptimizationCancelled(Exception):
    """The user clicked the Stop button to cancel optimization."""


class OptimizerRunner(QRunnable):
    """Object that can drive optimizers in a background thread."""

    class Signals(QObject):
        """Collection of signals provided by the runner."""

        actors_updated = pyqtSignal(np.ndarray, np.ndarray)
        constraints_updated = pyqtSignal(np.ndarray, BoundedArray)
        objective_updated = pyqtSignal(np.ndarray, np.ndarray)
        optimisation_finished = pyqtSignal(bool)

    signals = Signals()

    def __init__(self, optimizer: t.Optional[BaseOptimizer]):
        super().__init__()
        self.optimizer = optimizer
        self.objectives_log = []
        self.actions_log = []
        self.constraints_log = []
        self._is_cancelled = False
        self.x_0: t.Optional[np.ndarray] = None
        if optimizer:
            self.x_0 = optimizer.env.get_initial_params()

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
        # Yield at least once per optimization step. This releases
        # Python's Global Interpreter Lock (GIL) and gives the main
        # thread a chance to process GUI events.
        QThread.yieldCurrentThread()
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

    @pyqtSlot()
    def run(self):
        # pylint: disable = bare-except
        try:
            if self.x_0 is None:
                raise TypeError("Cannot run without optimizer")
            optimum = self.optimizer.solve(self._env_callback, self.x_0.copy())
            self._env_callback(optimum)
        except OptimizationCancelled:
            LOG.info("Manually cancelled optimization")
        except:
            sys.excepthook(*sys.exc_info())
            LOG.error("Aborted optimization due to the above exception")
        self.signals.optimisation_finished.emit(True)


def all_into_flat_array(values: t.Iterable[t.Union[float, np.ndarray]]) -> np.ndarray:
    """Dump arrays, scalars, etc. into a flat NumPy array."""
    flat_arrays = [np.asanyarray(value).flatten() for value in values]
    return np.concatenate(flat_arrays) if flat_arrays else np.array([])
