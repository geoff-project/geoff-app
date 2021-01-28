"""Adapters for all provided single-objective optimizers."""

import logging
import typing as t
from types import SimpleNamespace

import numpy as np
import pybobyqa
import scipy.optimize
from cernml import coi

from .base_optimizer import BaseOptimizer

LOG = logging.getLogger(__name__)


class OptimizationFailed(Exception):
    """Optimization failed for some reason."""


class BobyQA(BaseOptimizer):
    """Adapter for the BobyQA algorithm."""

    def __init__(self, env: coi.SingleOptimizable):
        self.maxfun = 100
        self.rhobeg = 0.1
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
            "rhobeg",
            self.rhobeg,
            range=(0.0, 1.0),
            help="Initial size of the trust region",
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
        self.rhobeg = values.rhobeg
        self.rhoend = values.rhoend
        self.seek_global_minimum = values.seek_global_minimum
        self.objfun_has_noise = values.objfun_has_noise

    def solve(self, func, x_0):
        bounds = (-np.ones(x_0.shape), np.ones(x_0.shape))
        opt_result = pybobyqa.solve(
            func,
            x0=x_0,
            bounds=bounds,
            rhobeg=self.rhobeg,
            rhoend=self.rhoend,
            maxfun=self.maxfun,
            seek_global_minimum=self.seek_global_minimum,
            objfun_has_noise=self.objfun_has_noise,
        )
        log_level = {
            opt_result.EXIT_SUCCESS: logging.INFO,
            opt_result.EXIT_MAXFUN_WARNING: logging.WARNING,
            opt_result.EXIT_SLOW_WARNING: logging.WARNING,
            opt_result.EXIT_FALSE_SUCCESS_WARNING: logging.WARNING,
            opt_result.EXIT_INPUT_ERROR: logging.ERROR,
            opt_result.EXIT_TR_INCREASE_ERROR: logging.ERROR,
            opt_result.EXIT_LINALG_ERROR: logging.ERROR,
        }.get(opt_result.flag, logging.ERROR)
        LOG.log(log_level, opt_result.msg)
        if log_level == logging.ERROR:
            raise OptimizationFailed(opt_result.msg)
        return opt_result.x


class Cobyla(BaseOptimizer):
    """Adapter for the COBYLA algorithm."""

    def __init__(self, env: coi.SingleOptimizable):
        self.maxfun = 100
        self.rhobeg = 1.0
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
            "rhobeg",
            self.rhobeg,
            range=(0.0, 1.0),
            help="Reasonable initial changes to the variables",
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
        self.rhobeg = values.rhobeg
        self.rhoend = values.rhoend

    def solve(self, func, x_0):
        constraints = list(self.wrapped_constraints)
        constraints.append(scipy.optimize.NonlinearConstraint(np.abs, 0.0, 1.0))
        result = scipy.optimize.minimize(
            func,
            method="COBYLA",
            x0=x_0,
            constraints=constraints,
            options=dict(maxiter=self.maxfun, rhobeg=self.rhobeg, tol=self.rhoend),
        )
        if result.success:
            LOG.info(result.message)
        else:
            LOG.error(result.message)
            raise OptimizationFailed(result.message)
        return result.x


ALL_ALGOS: t.Dict[str, BaseOptimizer] = {
    "BobyQA": BobyQA,
    "COBYLA": Cobyla,
}
