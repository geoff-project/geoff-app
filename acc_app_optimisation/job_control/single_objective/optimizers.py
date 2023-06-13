# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

import abc
import logging
import typing as t
from types import SimpleNamespace

import numpy as np
import pybobyqa
import scipy.optimize
import skopt.optimizer
from cernml import coi, extremum_seeking

from .constraints import Constraint, NonlinearConstraint

Optimizable = t.Union[coi.SingleOptimizable, coi.FunctionOptimizable]
Objective = t.Callable[[np.ndarray], float]
SolveFunc = t.Callable[[Objective, np.ndarray], np.ndarray]


LOG = logging.getLogger(__name__)


class OptimizationFailed(Exception):
    """Optimization failed for some reason."""


class OptimizerFactory(abc.ABC):
    @abc.abstractmethod
    def make_solve_func(
        self,
        bounds: scipy.optimize.Bounds,
        constraints: t.Sequence[Constraint],
    ) -> SolveFunc:
        raise NotImplementedError()


class Bobyqa(OptimizerFactory, coi.Configurable):
    def __init__(self) -> None:
        self.maxfun = 100
        self.rhobeg = 0.5
        self.rhoend = 0.05
        self.nsamples = 1
        self.seek_global_minimum = False
        self.objfun_has_noise = False

    def make_solve_func(
        self,
        bounds: scipy.optimize.Bounds,
        constraints: t.Sequence[Constraint],
    ) -> SolveFunc:
        def solve(objective: Objective, x_0: np.ndarray) -> np.ndarray:
            nsamples = self.nsamples
            opt_result = pybobyqa.solve(
                objective,
                x0=x_0,
                bounds=(bounds.lb, bounds.ub),
                rhobeg=self.rhobeg,
                rhoend=self.rhoend,
                maxfun=self.maxfun,
                seek_global_minimum=self.seek_global_minimum,
                objfun_has_noise=self.objfun_has_noise,
                nsamples=lambda *_: nsamples,
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

        return solve

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
            range=(1e-10, 1.0),
            help="Initial size of the trust region",
        )
        config.add(
            "rhoend",
            self.rhoend,
            range=(1e-10, 1.0),
            help="Step size below which the optimization is considered converged",
        )
        config.add(
            "nsamples",
            self.nsamples,
            range=(1, 100),
            help="Number of measurements which to average over in each iteration",
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
        if values.rhobeg <= values.rhoend:
            raise coi.BadConfig("rhobeg must be greater than rhoend")
        self.maxfun = values.maxfun
        self.rhobeg = values.rhobeg
        self.rhoend = values.rhoend
        self.nsamples = values.nsamples
        self.seek_global_minimum = values.seek_global_minimum
        self.objfun_has_noise = values.objfun_has_noise


class Cobyla(OptimizerFactory, coi.Configurable):
    """Adapter for the COBYLA algorithm."""

    def __init__(self) -> None:
        self.maxfun = 100
        self.rhobeg = 1.0
        self.rhoend = 0.05

    def make_solve_func(
        self,
        bounds: scipy.optimize.Bounds,
        constraints: t.Sequence[Constraint],
    ) -> SolveFunc:
        constraints = list(constraints)
        constraints.append(NonlinearConstraint(lambda x: x, bounds.lb, bounds.ub))

        def solve(objective: Objective, x_0: np.ndarray) -> np.ndarray:
            result = scipy.optimize.minimize(
                objective,
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

        return solve

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


class NelderMead(OptimizerFactory, coi.Configurable):
    """Adapter for the Nelder–Mead algorithm."""

    DELTA_IF_ZERO: t.ClassVar[float] = 0.001
    DELTA_IF_NONZERO: t.ClassVar[float] = 0.05

    def __init__(self) -> None:
        self.maxfun = 100
        self.adaptive = False
        self.tolerance = 0.05
        self.delta_if_zero = self.DELTA_IF_ZERO
        self.delta_if_nonzero = self.DELTA_IF_NONZERO

    def make_solve_func(
        self,
        bounds: scipy.optimize.Bounds,
        constraints: t.Sequence[Constraint],
    ) -> SolveFunc:
        def solve(objective: Objective, x_0: np.ndarray) -> np.ndarray:
            result = scipy.optimize.minimize(
                objective,
                method="Nelder-Mead",
                x0=x_0,
                tol=self.tolerance,
                bounds=bounds,
                options=dict(
                    maxfev=self.maxfun,
                    adaptive=self.adaptive,
                    initial_simplex=self._build_simplex(x_0),
                ),
            )
            if result.success:
                LOG.info(result.message)
            else:
                LOG.error(result.message)
                raise OptimizationFailed(result.message)
            return result.x

        return solve

    def get_config(self) -> coi.Config:
        config = coi.Config()
        config.add(
            "maxfun",
            self.maxfun,
            range=(0, np.inf),
            help="Maximum number of function evaluations",
        )
        config.add(
            "adaptive",
            self.adaptive,
            help="Adapt algorithm parameters to dimensionality of problem",
        )
        config.add(
            "tolerance",
            self.tolerance,
            range=(0.0, 1.0),
            help="Convergence tolerance",
        )
        config.add(
            "delta_if_nonzero",
            self.delta_if_nonzero,
            range=(-1.0, 1.0),
            default=self.DELTA_IF_NONZERO,
            help="Relative change to nonzero entries to get initial simplex",
        )
        config.add(
            "delta_if_zero",
            self.delta_if_zero,
            range=(-1.0, 1.0),
            default=self.DELTA_IF_ZERO,
            help="Absolute addition to zero entries to get initial simplex",
        )
        return config

    def apply_config(self, values: SimpleNamespace) -> None:
        self.maxfun = values.maxfun
        self.adaptive = values.adaptive
        self.tolerance = values.tolerance
        self.delta_if_nonzero = values.delta_if_nonzero
        self.delta_if_zero = values.delta_if_zero

    def _build_simplex(self, x_0: np.ndarray) -> np.ndarray:
        """Build an initial simplex based on an initial point.

        This is identical to the simplex construction in Scipy, but
        makes the two scaling factors (``nonzdelt`` and ``zdelt``)
        configurable.

        See https://github.com/scipy/scipy/blob/master/scipy/optimize/optimize.py
        """
        dim = len(x_0)
        simplex = np.empty((dim + 1, dim), dtype=x_0.dtype)
        simplex[0] = x_0
        for i in range(dim):
            point = x_0.copy()
            if point[i] != 0.0:
                point[i] *= 1 + self.delta_if_nonzero
            else:
                point[i] = self.delta_if_zero
            simplex[i + 1] = point
        return simplex


class Powell(OptimizerFactory, coi.Configurable):
    """Adapter for the Powell's conjugate-direction method."""

    def __init__(self) -> None:
        self.maxfun = 100
        self.tolerance = 0.05
        self.initial_step_size = 1.0

    def make_solve_func(
        self,
        bounds: scipy.optimize.Bounds,
        constraints: t.Sequence[Constraint],
    ) -> SolveFunc:
        def solve(objective: Objective, x_0: np.ndarray) -> np.ndarray:
            result = scipy.optimize.minimize(
                objective,
                method="Powell",
                x0=x_0,
                tol=self.tolerance,
                bounds=bounds,
                options=dict(
                    maxfev=self.maxfun,
                    direc=self.initial_step_size * np.eye(len(x_0)),
                ),
            )
            if result.success:
                LOG.info(result.message)
            else:
                LOG.error(result.message)
                raise OptimizationFailed(result.message)
            return result.x

        return solve

    def get_config(self) -> coi.Config:
        config = coi.Config()
        config.add(
            "maxfun",
            self.maxfun,
            range=(0, np.inf),
            help="Maximum number of function evaluations",
        )
        config.add(
            "tolerance",
            self.tolerance,
            range=(0.0, 1.0),
            help="Convergence tolerance",
        )
        config.add(
            "initial_step_size",
            self.initial_step_size,
            range=(1e-3, 1.0),
            help="Step size for the first iteration",
        )
        return config

    def apply_config(self, values: SimpleNamespace) -> None:
        self.maxfun = values.maxfun
        self.tolerance = values.tolerance
        self.initial_step_size = values.initial_step_size


class SkoptGpOptimize(OptimizerFactory, coi.Configurable):
    """Adapter for Bayesian optimization via scikit-optimize."""

    def __init__(self) -> None:
        self.check_convergence = False
        self.min_objective = 0.0
        self.n_calls = 100
        self.n_initial_points = 10
        self.acq_func = "LCB"
        self.kappa_param = 1.96
        self.xi_param = 0.01

    def make_solve_func(
        self,
        bounds: scipy.optimize.Bounds,
        constraints: t.Sequence[Constraint],
    ) -> SolveFunc:
        callback = (
            (lambda res: res.fun < self.min_objective)
            if self.check_convergence
            else None
        )

        def solve(objective: Objective, x_0: np.ndarray) -> np.ndarray:
            result = skopt.optimizer.gp_minimize(
                objective,
                x0=list(x_0),
                dimensions=zip(bounds.lb, bounds.ub),
                n_calls=self.n_calls,
                n_initial_points=self.n_initial_points,
                acq_func=self.acq_func,
                kappa=self.kappa_param,
                xi=self.xi_param,
                verbose=True,
                callback=callback,
            )
            return result.x

        return solve

    def get_config(self) -> coi.Config:
        config = coi.Config()
        config.add(
            "n_calls",
            self.n_calls,
            range=(0, np.inf),
            help="Maximum number of function evaluations",
        )
        config.add(
            "n_initial_points",
            self.n_initial_points,
            range=(0, np.inf),
            help="Number of function evaluations before approximating "
            "with base estimator",
        )
        config.add(
            "acq_func",
            self.acq_func,
            choices=["LCB", "EI", "PI", "EIps", "PIps"],
            help="Function to minimize over the Gaussian prior",
        )
        config.add(
            "kappa_param",
            self.kappa_param,
            range=(0, np.inf),
            help='Only used with "LCB". Controls how much of the '
            "variance in the predicted values should be taken into "
            "account. If set to be very high, then we are favouring "
            "exploration over exploitation and vice versa.",
        )
        config.add(
            "xi_param",
            self.xi_param,
            range=(0, np.inf),
            help='Only used with "EI", "PI" and variants. Controls '
            "how much improvement one wants over the previous best "
            "values.",
        )
        config.add(
            "check_convergence",
            self.check_convergence,
            help="Enable convergence check at every iteration. "
            "Without this, the algorithm always evaluates the "
            "function the maximum number of times.",
        )
        config.add(
            "min_objective",
            self.min_objective,
            help="If convergence check is enabled, end optimization "
            "below this value of the objective function.",
        )
        return config

    def apply_config(self, values: SimpleNamespace) -> None:
        if values.n_initial_points > values.n_calls:
            raise coi.BadConfig("n_initial_points must be less than maxfun")
        self.n_calls = values.n_calls
        self.n_initial_points = values.n_initial_points
        self.acq_func = values.acq_func
        self.kappa_param = values.kappa_param
        self.xi_param = values.xi_param
        self.check_convergence = values.check_convergence
        self.min_objective = values.min_objective


class ExtremumSeeking(OptimizerFactory, coi.Configurable):
    """Adapter for extremum seeking control."""

    def __init__(self) -> None:
        self.check_convergence = False
        self.max_calls = 0
        self.check_goal = False
        self.cost_goal = 0.0
        self.gain = 0.2
        self.oscillation_size = 0.1
        self.oscillation_sampling = 10
        self.decay_rate = 1.0

    def make_solve_func(
        self,
        bounds: scipy.optimize.Bounds,
        constraints: t.Sequence[Constraint],
    ) -> SolveFunc:
        def solve(objective: Objective, x_0: np.ndarray) -> np.ndarray:
            result = extremum_seeking.optimize(
                objective,
                x0=x_0,
                max_calls=self.max_calls if self.max_calls else None,
                cost_goal=self.cost_goal if self.check_goal else None,
                bounds=(bounds.lb, bounds.ub),
                gain=self.gain,
                oscillation_size=self.oscillation_size,
                oscillation_sampling=self.oscillation_sampling,
                decay_rate=self.decay_rate,
            )
            return result.params

        return solve

    def get_config(self) -> coi.Config:
        config = coi.Config()
        config.add(
            "max_calls",
            self.max_calls,
            range=(0, np.inf),
            help="Maximum number of function evaluations; if zero, there is no limit",
        )
        config.add(
            "check_goal",
            self.check_goal,
            help="If enabled, stop optimization when the objective "
            "function is below this value",
        )
        config.add(
            "cost_goal",
            self.cost_goal,
            help="If check_goal is enabled, end optimization when "
            "the objective goes below this value; if check_goal is "
            "disabled, this does nothing",
        )
        config.add(
            "gain",
            self.gain,
            range=(0.0, np.inf),
            help="Scaling factor applied to the objective function",
        )
        config.add(
            "oscillation_size",
            self.oscillation_size,
            range=(0.0, 1.0),
            help="Amplitude of the dithering oscillations; higher "
            "values make the parameters fluctuate stronger",
        )
        config.add(
            "oscillation_sampling",
            self.oscillation_sampling,
            range=(1, np.inf),
            help="Number of samples per dithering period; higher "
            "values make the parameters fluctuate slower",
        )
        config.add(
            "decay_rate",
            self.decay_rate,
            range=(0.0, 1.0),
            help="Decrease oscillation_size by this factor after every iteration",
        )
        return config

    def apply_config(self, values: SimpleNamespace) -> None:
        if values.gain == 0.0:
            raise coi.BadConfig("gain must not be zero")
        if values.oscillation_size == 0.0:
            raise coi.BadConfig("oscillation_size must not be zero")
        if values.decay_rate == 0.0:
            raise coi.BadConfig("decay_rate must not be zero")
        self.max_calls = values.max_calls
        self.check_goal = values.check_goal
        self.cost_goal = values.cost_goal
        self.gain = values.gain
        self.oscillation_size = values.oscillation_size
        self.oscillation_sampling = values.oscillation_sampling
        self.decay_rate = values.decay_rate


ALL_OPTIMIZERS: t.Mapping[str, t.Type[OptimizerFactory]] = {
    "BOBYQA": Bobyqa,
    "COBYLA": Cobyla,
    "Nelder–Mead": NelderMead,
    "Powell": Powell,
    "BayesOpt": SkoptGpOptimize,
    "Extremum Seeking": ExtremumSeeking,
}
