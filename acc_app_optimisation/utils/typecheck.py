"""Type checks against interfaces from `cernml.coi`.

The checks in this module automatically ensure to take wrappers into consideration.
"""

from __future__ import annotations

import typing as t

from cernml.coi import Configurable, FunctionOptimizable, Problem, SingleOptimizable
from gym import Env

if t.TYPE_CHECKING:  # pragma: no cover
    import sys

    if sys.version_info >= (3, 10):
        from typing import TypeGuard
    else:
        from typing_extensions import TypeGuard

__all__ = [
    "AnyOptimizable",
    "Env",
    "FunctionOptimizable",
    "Problem",
    "SingleOptimizable",
    "is_any_optimizable",
    "is_env",
    "is_function_optimizable",
    "is_single_optimizable",
]


AnyOptimizable = t.Union[SingleOptimizable, FunctionOptimizable]


def is_single_optimizable(problem: Problem) -> TypeGuard[SingleOptimizable]:
    return isinstance(problem.unwrapped, SingleOptimizable)


def is_function_optimizable(problem: Problem) -> TypeGuard[FunctionOptimizable]:
    return isinstance(problem.unwrapped, FunctionOptimizable)


def is_any_optimizable(problem: Problem) -> TypeGuard[AnyOptimizable]:
    return isinstance(problem.unwrapped, (SingleOptimizable, FunctionOptimizable))


def is_env(problem: Problem) -> TypeGuard[Env]:
    return isinstance(problem.unwrapped, Env)


def is_configurable(obj: t.Any) -> TypeGuard[Configurable]:
    obj = getattr(obj, "unwrapped", None)
    return isinstance(obj, Configurable)
