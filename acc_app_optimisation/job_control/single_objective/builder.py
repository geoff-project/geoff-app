import typing as t
from logging import getLogger

import numpy as np
from cernml.coi import cancellation

from ...envs import make_env_by_name
from ...utils.typecheck import (
    is_any_optimizable,
    is_function_optimizable,
    is_single_optimizable,
)
from ..base import CannotBuildJob, JobBuilder
from . import jobs, optimizers

if t.TYPE_CHECKING:
    from pyjapc import PyJapc  # pylint: disable=import-error, unused-import

LOG = getLogger(__name__)


class OptJobBuilder(JobBuilder):
    japc: t.Optional["PyJapc"]
    skeleton_points: t.Optional[np.ndarray]
    optimizer_factory: t.Optional[optimizers.OptimizerFactory]
    signals: jobs.Signals

    def __init__(self) -> None:
        self._problem: t.Optional[optimizers.Optimizable] = None
        self._problem_id = ""
        self._token_source = cancellation.TokenSource()
        self.japc = None
        self.skeleton_points = None
        self.optimizer_factory = None
        self.signals = jobs.Signals()

    @property
    def problem_id(self) -> str:
        return self._problem_id

    @problem_id.setter
    def problem_id(self, new_value: str) -> None:
        if new_value != self._problem_id:
            self.unload_problem()
        self._problem_id = new_value

    @property
    def problem(self) -> t.Optional[optimizers.Optimizable]:
        return self._problem

    def make_problem(self) -> optimizers.Optimizable:
        if not self.problem_id:
            raise CannotBuildJob("no optimization problem selected")
        self.unload_problem()
        problem = t.cast(
            optimizers.Optimizable,
            make_env_by_name(
                self.problem_id,
                make_japc=self._get_japc_or_raise,
                token=self._token_source.token,
            ),
        )
        assert is_any_optimizable(problem), type(problem.unwrapped)
        self._problem = problem
        return problem

    def _get_japc_or_raise(self) -> "PyJapc":
        if self.japc is None:
            raise CannotBuildJob("no LSA context selected")
        LOG.debug("Using selector %s", self.japc.getSelector())
        return self.japc

    def unload_problem(self) -> None:
        if self._problem is not None:
            LOG.debug("Closing %s", self.problem)
            self._problem.close()
            self._problem = None

    def build_job(self) -> jobs.OptJob:
        if self.optimizer_factory is None:
            raise CannotBuildJob("no optimizer selected")
        problem = self.make_problem() if self.problem is None else self.problem
        if is_function_optimizable(problem):
            if self.skeleton_points is None or not np.shape(self.skeleton_points):
                raise CannotBuildJob("no skeleton points selected")
            return jobs.FunctionOptimizableJob(
                token_source=self._token_source,
                signals=self.signals,
                optimizer_factory=self.optimizer_factory,
                problem=problem,
                skeleton_points=self.skeleton_points,
            )
        assert is_single_optimizable(problem), problem.unwrapped
        return jobs.SingleOptimizableJob(
            token_source=self._token_source,
            signals=self.signals,
            optimizer_factory=self.optimizer_factory,
            problem=problem,
        )
