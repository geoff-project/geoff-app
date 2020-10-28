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
        objetive_updated = pyqtSignal(np.ndarray, np.ndarray)
        optimisation_finished = pyqtSignal(bool)

    iteration_counter = 0
    iterations = []
    objectives = []
    signals = Signals()

    def __init__(self):
        super().__init__()
        self.optimizer = None

    def setOptimizer(self, optimizer: AbstractSingleObjectiveOptimizer):
        self.optimizer = optimizer

    def getOptimizer(self):
        return self.optimizer

    def _env_callback(self, a):
        self.iteration_counter += 1
        self.iterations.append(self.iteration_counter)
        loss = self.optimizer.env.compute_single_objective(a.copy())
        self.objectives.append(np.squeeze(loss))
        self.signals.objetive_updated.emit(
            np.array(self.iterations), np.array(self.objectives)
        )
        return loss

    def solve(self):
        self.iteration_counter = 0
        self.iterations = []
        self.objectives = []
        optimum = self.optimizer.solve(self._env_callback, **self.optimizer.opt_params)
        self._env_callback(optimum)
        self.signals.optimisation_finished.emit(True)

    def update_opt_param(self, keyword, value):
        if keyword in self.optimizer.opt_params:
            self.optimizer.opt_params[keyword] = value

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
