#!/usr/bin/env python
"""Tests for `acc_app_optimisation.utils.layouts`."""

# pylint: disable = missing-function-docstring
# pylint: disable = missing-class-docstring
# pylint: disable = redefined-outer-name

import typing as t
from unittest.mock import Mock

import numpy as np
import pytest
from cernml import coi
from PyQt5 import QtCore
from pytest_mock import MockerFixture
from scipy.optimize import NonlinearConstraint

from acc_app_optimisation.algos.single_opt import (
    ALL_ALGOS,
    BaseOptimizer,
    OptimizerRunner,
)


def make_mock_constraint(shape: t.Tuple[int, ...]) -> NonlinearConstraint:
    constraint = NonlinearConstraint(Mock(), 0.0, 1.0)
    constraint.fun.return_value = np.random.uniform(-1.0, 1.0, size=shape)
    return constraint


@pytest.fixture(scope="module")
def threadpool() -> QtCore.QThreadPool:
    return QtCore.QThreadPool.globalInstance()


@pytest.fixture
def optimizable() -> coi.SingleOptimizable:
    result = Mock(spec=coi.SingleOptimizable, autospec=coi.SingleOptimizable)
    result.unwrapped = result
    result.metadata = {"render.modes": []}
    result.constraints = [
        make_mock_constraint(shape=()),
        make_mock_constraint(shape=(3,)),
    ]
    result.compute_single_objective.side_effect = np.linalg.norm
    result.get_initial_params.return_value = np.arange(3.0, 6.0)
    result.spec = Mock(id=str(result))
    return result


@pytest.mark.parametrize("optimizer_class", ALL_ALGOS.values())
def test_runner(
    mocker: MockerFixture,
    threadpool: QtCore.QThreadPool,
    optimizable: coi.SingleOptimizable,
    *,
    optimizer_class: t.Type[BaseOptimizer],
) -> None:
    # Given:
    mocker.patch("numpy.clip", side_effect=lambda x, lower, upper: x)
    recv = Mock()
    runner = OptimizerRunner()
    runner.set_problem(optimizable)
    runner.set_optimizer_class(optimizer_class)
    runner.signals.actors_updated.connect(recv.actors_updated)
    runner.signals.objective_updated.connect(recv.objective_updated)
    runner.signals.constraints_updated.connect(recv.constraints_updated)
    runner.signals.optimisation_finished.connect(recv.optimisation_finished)
    # When:
    threadpool.start(runner.create_job())
    threadpool.waitForDone()
    # Then:
    optimizable.get_initial_params.assert_called_once_with()
    steps = optimizable.compute_single_objective.call_count
    assert steps >= 20
