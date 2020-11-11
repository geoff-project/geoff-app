"""Module containing single-objective optimizers."""

import sys

import numpy as np
import pybobyqa
from cernml.coi import SingleOptimizable
from scipy.optimize import fmin_cobyla, minimize, NonlinearConstraint
from PyQt5.QtCore import pyqtSignal, QObject, QRunnable, QThread, pyqtSlot


class OptimizationCancelled(Exception):
    """The user clicked the Stop button to cancel optimization."""


class AbstractSingleObjectiveOptimizer:
    def __init__(self, env: SingleOptimizable, opt_params):
        self.env = env
        self.opt_params = opt_params

    def solve(self, func, **kwargs):
        raise NotImplementedError()


class OptimizerRunner(QRunnable):
    class Signals(QObject):
        actors_updated = pyqtSignal(np.ndarray, np.ndarray)
        objective_updated = pyqtSignal(np.ndarray, np.ndarray)
        optimisation_finished = pyqtSignal(bool)

    signals = Signals()

    def __init__(self, optimizer: AbstractSingleObjectiveOptimizer):
        super().__init__()
        self.optimizer = optimizer
        self.objectives = []
        self.actors = []
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def _env_callback(self, action):
        if self._is_cancelled:
            raise OptimizationCancelled()
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
        # Log inputs and outputs.
        self.actors.append(np.squeeze(action))
        self.objectives.append(np.squeeze(loss))
        iterations = np.arange(len(self.objectives))
        self.signals.objective_updated.emit(
            iterations,
            np.array(self.objectives),
        )
        self.signals.actors_updated.emit(
            iterations,
            np.array(self.actors),
        )
        return loss

    def solve(self):
        try:
            optimum = self.optimizer.solve(
                self._env_callback, **self.optimizer.opt_params
            )
            self._env_callback(optimum)
        except OptimizationCancelled:
            pass
        except:
            sys.excepthook(*sys.exc_info())
            print("Aborted optimization due to the above exception", file=sys.stderr)
        self.signals.optimisation_finished.emit(True)

    @pyqtSlot()
    def run(self):
        self.solve()


class BobyQaAlgo(AbstractSingleObjectiveOptimizer):
    def __init__(self, env: SingleOptimizable):
        opt_params = {
            "seek_global_minimum": False,
            "maxfun": 100,
            "rhoend": 0.05,
            "objfun_has_noise": False,
        }
        super().__init__(env, opt_params)

    def solve(self, func, **kwargs):
        x_0 = self.env.get_initial_params()
        bounds = (-np.ones(x_0.shape), np.ones(x_0.shape))
        opt_result = pybobyqa.solve(func, x0=x_0, rhobeg=1.0, bounds=bounds, **kwargs)
        return opt_result.x


class CobylaAlgo(AbstractSingleObjectiveOptimizer):
    def __init__(self, env: SingleOptimizable):
        opt_params = {
            "maxiter": 100,
            "tol": 0.05,
        }
        super().__init__(env, opt_params)

    def solve(self, func, **kwargs):
        x_0 = self.env.get_initial_params()
        constraints = list(self.env.constraints)
        constraints.append(NonlinearConstraint(lambda x: np.abs(x), 0.0, 1.0))
        result = minimize(
            func,
            method="COBYLA",
            x0=x_0,
            constraints=constraints,
            options=dict(kwargs, rhobeg=1.0),
        )
        return result.x


all_single_algos_dict = {
    "BOBYQA": BobyQaAlgo,
    "COBYLA": CobylaAlgo,
}
