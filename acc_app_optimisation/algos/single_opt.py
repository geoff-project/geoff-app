"""Module containing single-objective optimizers."""

import numpy as np
import pybobyqa
from cernml.coi import SingleOptimizable
from scipy.optimize import fmin_cobyla
from PyQt5.QtCore import pyqtSignal, QObject, QRunnable, pyqtSlot


class AlgoSingleOptSignals(QObject):
    objetive_updated = pyqtSignal(np.ndarray, np.ndarray)
    optimisation_finished = pyqtSignal(bool)


class AlgoSingleBase(QRunnable):

    opt_params = {}
    opt_callback = None
    iteration_counter = 0
    iterations = []
    objectives = []
    signals = AlgoSingleOptSignals()

    def _env_callback(self, a):
        self.iteration_counter += 1
        self.iterations.append(self.iteration_counter)
        loss = self.env.compute_single_objective(a.copy())
        self.objectives.append(np.squeeze(loss))
        self.signals.objetive_updated.emit(
            np.array(self.iterations), np.array(self.objectives)
        )
        return loss

    def solve(self):
        self.iteration_counter = 0
        self.iterations = []
        self.objectives = []
        optimum = self.opt_callback(self._env_callback, **self.opt_params)
        self._env_callback(optimum)
        self.signals.optimisation_finished.emit(True)

    def update_opt_param(self, keyword, value):
        if keyword in self.opt_params:
            self.opt_params.update({keyword: value})

    @pyqtSlot()
    def run(self):
        self.solve()


class BobyQaAlgo(AlgoSingleBase):
    def __init__(self, env: SingleOptimizable):
        super().__init__()
        self.env = env
        x_0 = env.get_initial_params()
        bounds_0 = (
            np.ones(env.optimization_space.shape[-1]) * (-1.0),
            np.ones(env.optimization_space.shape[-1]) * 1.0,
        )
        self.opt_params = {
            "x0": x_0,
            "bounds": bounds_0,
            "rhobeg": 1.0,
            "seek_global_minimum": False,
            "maxfun": 100,
            "rhoend": 0.05,
            "objfun_has_noise": False,
        }
        self.opt_callback = lambda *args, **kwargs: pybobyqa.solve(*args, **kwargs).x


class CobylaAlgo(AlgoSingleBase):
    def constr1(self, x):
        return 1.0 - np.abs(x)

    def __init__(self, env: SingleOptimizable):
        super().__init__()
        self.env = env
        x_0 = env.get_initial_params()
        bounds_0 = (
            np.ones(env.optimization_space.shape[-1]) * (-1.0),
            np.ones(env.optimization_space.shape[-1]) * 1.0,
        )
        self.opt_params = {
            "x0": x_0,
            "cons": [self.constr1],
            "rhobeg": 1.0,
            "maxfun": 100,
            "rhoend": 0.05,
        }
        self.opt_callback = fmin_cobyla


all_single_algos_dict = {"BOBYQA": BobyQaAlgo, "COBYLA": CobylaAlgo}
