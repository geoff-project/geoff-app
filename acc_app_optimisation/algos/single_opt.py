"""Module containing single-objective optimizers."""

import sys
from types import SimpleNamespace

import numpy as np
import pybobyqa
from cernml import coi
from PyQt5.QtCore import pyqtSignal, QObject, QRunnable, QThread, pyqtSlot
import scipy.optimize


class OptimizationCancelled(Exception):
    """The user clicked the Stop button to cancel optimization."""


class AbstractSingleObjectiveOptimizer(coi.Configurable):
    def __init__(self, env: coi.SingleOptimizable):
        self.env = env

    def solve(self, func):
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
        # Log inputs and outputs.
        self._log_inputs_outputs(action, loss)
        self._render_env()
        return loss

    def _log_inputs_outputs(self, action, loss):
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

    def _render_env(self):
        env = self.optimizer.env
        if "matplotlib_figures" not in env.metadata.get("render.modes", []):
            return
        figures = env.render(mode="matplotlib_figures")
        for figure in figures:
            figure.canvas.draw_idle()

    def solve(self):
        try:
            optimum = self.optimizer.solve(self._env_callback)
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
    def __init__(self, env: coi.SingleOptimizable):
        self.maxfun = 100
        self.rhoend = 0.05
        self.seek_global_minimum = False
        self.objfun_has_noise = False
        super().__init__(env)

    def get_config(self) -> coi.Config:
        config = coi.Config()
        config.add(
            "maxfun",
            self.maxfun,
            range=(0, np.inf),
            help="Maximum number of function evaluations",
        )
        config.add(
            "rhoend",
            self.rhoend,
            range=(0.0, 1.0),
            help="Step size below which the optimization is considered converged",
        )
        config.add(
            "seek_global_minimum",
            self.seek_global_minimum,
            help="Enable additional logic to avoid local minima",
        )
        config.add(
            "objfun_has_noise",
            self.objfun_has_noise,
            help="Enable additional logic to handle non-deterministic environments",
        )
        return config

    def apply_config(self, values: SimpleNamespace) -> None:
        self.maxfun = values.maxfun
        self.rhoend = values.rhoend
        self.seek_global_minimum = values.seek_global_minimum
        self.objfun_has_noise = values.objfun_has_noise

    def solve(self, func):
        x_0 = self.env.get_initial_params()
        bounds = (-np.ones(x_0.shape), np.ones(x_0.shape))
        opt_result = pybobyqa.solve(
            func,
            x0=x_0,
            bounds=bounds,
            rhobeg=1.0,
            rhoend=self.rhoend,
            maxfun=self.maxfun,
            seek_global_minimum=self.seek_global_minimum,
            objfun_has_noise=self.objfun_has_noise,
        )
        return opt_result.x


class CobylaAlgo(AbstractSingleObjectiveOptimizer):
    def __init__(self, env: coi.SingleOptimizable):
        self.maxfun = 100
        self.rhoend = 0.05
        super().__init__(env)

    def get_config(self) -> coi.Config:
        config = coi.Config()
        config.add(
            "maxfun",
            self.maxfun,
            range=(0, np.inf),
            help="Maximum number of function evaluations",
        )
        config.add(
            "rhoend",
            self.rhoend,
            range=(0.0, 1.0),
            help="Step size below which the optimization is considered converged",
        )
        return config

    def apply_config(self, values: SimpleNamespace) -> None:
        self.maxfun = values.maxfun
        self.rhoend = values.rhoend

    def solve(self, func):
        x_0 = self.env.get_initial_params()
        constraints = list(self.env.constraints)
        constraints.append(scipy.optimize.NonlinearConstraint(np.abs, 0.0, 1.0))
        result = scipy.optimize.minimize(
            func,
            method="COBYLA",
            x0=x_0,
            constraints=constraints,
            options=dict(maxiter=self.maxfun, tol=self.rhoend, rhobeg=1.0),
        )
        return result.x


all_single_algos_dict = {
    "BOBYQA": BobyQaAlgo,
    "COBYLA": CobylaAlgo,
}
