# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

import typing as t

import numpy as np
from scipy.optimize import LinearConstraint, NonlinearConstraint

Constraint = t.Union[LinearConstraint, NonlinearConstraint]


class CachedNonlinearConstraint(NonlinearConstraint):
    """A nonlinear constraint that caches its results.

    This is an adapter class used for the `OptimizerRunner`. Subclasses
    of `BaseOptimizer` should not use it.

    The purpose of this class is to make the results of constraint
    evaluations available to the GUI without calling the constraint
    functions more than once per step.
    """

    def __init__(self, constraint: NonlinearConstraint) -> None:
        self.cache: t.Dict = {}

        def fun(params: t.Any) -> t.Any:
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

    def clear_cache(self) -> None:
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
