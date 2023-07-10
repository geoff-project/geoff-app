# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

import typing as t
from logging import getLogger

from cernml.coi import cancellation
from cernml.optimizers import Optimizer

from ...envs import make_env_by_name
from ...utils.typecheck import (
    AnyOptimizable,
    is_any_optimizable,
    is_function_optimizable,
    is_single_optimizable,
)
from ..base import CannotBuildJob, JobBuilder
from .jobs import FunctionOptimizableJob, OptJob, Signals, SingleOptimizableJob
from .skeleton_points import gather_skeleton_points

if t.TYPE_CHECKING:
    from pyjapc import PyJapc  # pylint: disable=import-error, unused-import

LOG = getLogger(__name__)


class OptJobBuilder(JobBuilder):
    japc: t.Optional["PyJapc"]
    skeleton_points: t.Tuple[float, ...]
    optimizer_factory: t.Optional[Optimizer]
    signals: Signals

    def __init__(self) -> None:
        self._problem: t.Optional[AnyOptimizable] = None
        self._problem_id = ""
        self._token_source = cancellation.TokenSource()
        self.japc = None
        self.skeleton_points = ()
        self.optimizer_factory = None
        self.signals = Signals()

    @property
    def problem_id(self) -> str:
        return self._problem_id

    @problem_id.setter
    def problem_id(self, new_value: str) -> None:
        if new_value != self._problem_id:
            self.unload_problem()
        self._problem_id = new_value

    @property
    def problem(self) -> t.Optional[AnyOptimizable]:
        return self._problem

    def make_problem(self) -> AnyOptimizable:
        if not self.problem_id:
            raise CannotBuildJob("no optimization problem selected")
        self.unload_problem()
        problem = t.cast(
            AnyOptimizable,
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

    def build_job(self) -> OptJob:
        if self.optimizer_factory is None:
            raise CannotBuildJob("no optimizer selected")
        problem = self.make_problem() if self.problem is None else self.problem
        if is_function_optimizable(problem):
            skeleton_points = gather_skeleton_points(problem, self.skeleton_points)
            return FunctionOptimizableJob(
                token_source=self._token_source,
                signals=self.signals,
                optimizer_factory=self.optimizer_factory,
                problem=problem,
                skeleton_points=skeleton_points,
            )
        assert is_single_optimizable(problem), problem.unwrapped
        return SingleOptimizableJob(
            token_source=self._token_source,
            signals=self.signals,
            optimizer_factory=self.optimizer_factory,
            problem=problem,
        )
