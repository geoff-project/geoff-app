"""Provide the base class of all single-objective optimizers."""

import typing as t

import numpy as np
from cernml import coi
from scipy.optimize import LinearConstraint, NonlinearConstraint

Constraint = t.Union[LinearConstraint, NonlinearConstraint]


class BaseOptimizer(coi.Configurable):
    """Base class of all single-objective optimizers.

    At the moment, this serves three purposes:
    - define the interface of all optimizers;
    - keep the `SingleOptimizable` problem around;
    - keep a list of `CachedNonlinearConstraint` around.

    The `CachedNonlinearConstraint` is used by the `OptimizerRunner` to
    send the values of the constraint functions to the GUI without
    executing the constraints a second time. This is necessary because
    constraint functions might potentially be expensive.
    """

    def __init__(self, env: coi.SingleOptimizable):
        self.env = env
        self.wrapped_constraints = [
            CachedNonlinearConstraint.from_any_constraint(c) for c in env.constraints
        ]

    def solve(self, func):
        """Solve the optimization problem."""
        raise NotImplementedError()


class CachedNonlinearConstraint(NonlinearConstraint):
    """A nonlinear constraint that caches its results.

    This is an adapter class used for the `OptimizerRunner`. Subclasses
    of `BaseOptimizer` should not use it.

    The purpose of this class is to make the results of constraint
    evaluations available to the GUI without calling the constraint
    functions more than once per step.
    """

    def __init__(self, constraint: NonlinearConstraint) -> None:
        self.cache = {}

        def fun(params):
            key = tuple(params)
            result = self.cache.get(key)
            if result is None:
                self.cache[key] = result = constraint.fun(params)
            return result

        super().__init__(
            fun=fun,
            lb=constraint.lb,
            ub=constraint.ub,
            jac=constraint.jac,
            hess=constraint.hess,
            keep_feasible=constraint.keep_feasible,
            finite_diff_rel_step=constraint.finite_diff_rel_step,
            finite_diff_jac_sparsity=constraint.finite_diff_jac_sparsity,
        )

    @classmethod
    def from_any_constraint(cls, constraint: Constraint) -> "CachedNonlinearConstraint":
        """Convert any kind of SciPy constraint into this type."""
        if isinstance(constraint, LinearConstraint):
            constraint = convert_linear_constraint(constraint)
        assert isinstance(constraint, NonlinearConstraint)
        return cls(constraint)

    def clear_cache(self):
        """Clear the cache of this constraint."""
        self.cache.clear()


def convert_linear_constraint(cons: LinearConstraint) -> NonlinearConstraint:
    """Turn a linear into a non-linear constraint."""
    return NonlinearConstraint(
        lambda x: np.dot(cons.A, x),
        cons.lb,
        cons.ub,
        cons.keep_feasible,
    )
