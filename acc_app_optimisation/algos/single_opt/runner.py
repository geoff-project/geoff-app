"""The runner for all optimizers."""

import logging
import sys

import numpy as np
from PyQt5.QtCore import pyqtSignal, QObject, QRunnable, QThread, pyqtSlot

from .base_optimizer import BaseOptimizer

LOG = logging.getLogger(__name__)


class OptimizationCancelled(Exception):
    """The user clicked the Stop button to cancel optimization."""


class OptimizerRunner(QRunnable):
    """Object that can drive optimizers in a background thread."""

    class Signals(QObject):
        """Collection of signals provided by the runner."""

        actors_updated = pyqtSignal(np.ndarray, np.ndarray)
        constraints_updated = pyqtSignal(np.ndarray, np.ndarray)
        objective_updated = pyqtSignal(np.ndarray, np.ndarray)
        optimisation_finished = pyqtSignal(bool)

    signals = Signals()

    def __init__(self, optimizer: BaseOptimizer):
        super().__init__()
        self.optimizer = optimizer
        self.objectives = []
        self.actors = []
        self.constraint_values = []
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
        # Calculate loss function.
        loss = env.compute_single_objective(action.copy())
        assert np.ndim(loss) == 0, "non-scalar loss"
        # Calculate constraints and mash all of them into a single array.
        constraint_values = np.concatenate(
            [
                np.asanyarray(constraint.fun(action)).flatten()
                for constraint in self.optimizer.wrapped_constraints
            ]
        )
        # Log inputs and outputs.
        self._log_inputs_outputs(action.copy().flatten(), loss, constraint_values)
        self._render_env()
        # Clear all constraint caches.
        for constraint in self.optimizer.wrapped_constraints:
            constraint.clear_cache()
        return loss

    def _log_inputs_outputs(self, action, loss, constraints):
        self.actors.append(action)
        self.objectives.append(loss)
        self.constraint_values.append(constraints)
        iterations = np.arange(len(self.objectives))
        self.signals.objective_updated.emit(
            iterations,
            np.array(self.objectives),
        )
        self.signals.actors_updated.emit(
            iterations,
            np.array(self.actors),
        )
        self.signals.constraints_updated.emit(
            iterations,
            np.array(self.constraint_values),
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
