"""Adapters for all provided single-objective optimizers."""

import typing as t
from types import SimpleNamespace

import numpy as np
import pybobyqa
import scipy.optimize
from cernml import coi

from .base_optimizer import BaseOptimizer


class BobyQA(BaseOptimizer):
    """Adapter for the BobyQA algorithm."""

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


class Cobyla(BaseOptimizer):
    """Adapter for the COBYLA algorithm."""

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
        constraints = list(self.wrapped_constraints)
        constraints.append(scipy.optimize.NonlinearConstraint(np.abs, 0.0, 1.0))
        result = scipy.optimize.minimize(
            func,
            method="COBYLA",
            x0=x_0,
            constraints=constraints,
            options=dict(maxiter=self.maxfun, tol=self.rhoend, rhobeg=1.0),
        )
        return result.x


ALL_ALGOS: t.Dict[str, BaseOptimizer] = {
    "BobyQA": BobyQA,
    "COBYLA": Cobyla,
}
