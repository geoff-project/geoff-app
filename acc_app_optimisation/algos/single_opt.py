"""Module containing single-objective optimizers."""

import numpy as np
import pybobyqa
from cernml.coi import SingleOptimizable
from scipy.optimize import fmin_cobyla
from PyQt5.QtCore import pyqtSignal, QObject, QRunnable, pyqtSlot


class AbstractSingleObjectiveOptimizer:
    def __init__(self, env, opt_params):
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

    def _env_callback(self, a):
        loss = self.optimizer.env.compute_single_objective(a.copy())
        self.objectives.append(np.squeeze(loss))
        self.actors.append(np.squeeze(a.copy()))
        iterations = np.arange(len(self.objectives))
        self.signals.objective_updated.emit(iterations, np.array(self.objectives))
        self.signals.actors_updated.emit(iterations, np.array(self.actors))
        return loss

    def solve(self):
        optimum = self.optimizer.solve(self._env_callback, **self.optimizer.opt_params)
        self._env_callback(optimum)
        self.signals.optimisation_finished.emit(True)

    @pyqtSlot()
    def run(self):
        self.solve()


class BobyQaAlgo(AbstractSingleObjectiveOptimizer):
    def __init__(self, env: SingleOptimizable):
        x_0 = env.get_initial_params()
        bounds = (-np.ones(x_0.shape), np.ones(x_0.shape))
        opt_params = {
            "x0": x_0,
            "bounds": bounds,
            "rhobeg": 1.0,
            "seek_global_minimum": False,
            "maxfun": 100,
            "rhoend": 0.05,
            "objfun_has_noise": False,
        }
        super().__init__(env, opt_params)

    def solve(self, func, **kwargs):
        opt_result = pybobyqa.solve(func, **kwargs)
        return opt_result.x


class CobylaAlgo(AbstractSingleObjectiveOptimizer):
    def __init__(self, env: SingleOptimizable):
        x_0 = env.get_initial_params()
        opt_params = {
            "x0": x_0,
            "cons": [lambda x: 1.0 - np.abs(x)],
            "rhobeg": 1.0,
            "maxfun": 100,
            "rhoend": 0.05,
        }
        super().__init__(env, opt_params)

    def solve(self, func, **kwargs):
        return fmin_cobyla(func, **kwargs)


all_single_algos_dict = {"BOBYQA": BobyQaAlgo, "COBYLA": CobylaAlgo}
