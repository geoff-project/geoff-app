# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

# pylint: disable = missing-function-docstring
# pylint: disable = missing-class-docstring
# pylint: disable = redefined-outer-name

"""Tests for `acc_app_optimisation.utils.layouts`."""

import typing as t
from unittest.mock import Mock

import cernml.coi
import gym.envs.registration
import numpy as np
import pytest
from PyQt5 import QtCore
from pytest_mock import MockerFixture
from scipy.optimize import NonlinearConstraint

from acc_app_optimisation.job_control.single_objective import (
    ALL_OPTIMIZERS,
    OptimizerFactory,
    OptJobBuilder,
)


def make_mock_constraint(shape: t.Tuple[int, ...]) -> NonlinearConstraint:
    return NonlinearConstraint(
        lambda _: np.random.uniform(-1.0, 1.0, size=shape), 0.0, 1.0
    )


@pytest.fixture(scope="module")
def threadpool() -> QtCore.QThreadPool:
    return QtCore.QThreadPool.globalInstance()


@pytest.fixture
def optimizable() -> cernml.coi.SingleOptimizable:
    result = Mock(
        spec=cernml.coi.SingleOptimizable, autospec=cernml.coi.SingleOptimizable
    )
    result.unwrapped = result
    result.metadata = {"render.modes": []}
    result.constraints = [
        make_mock_constraint(shape=()),
        make_mock_constraint(shape=(3,)),
    ]
    result.compute_single_objective.side_effect = np.linalg.norm
    result.optimization_space = gym.spaces.Box(-1.0, 1.0, shape=(3,))
    result.get_initial_params.return_value = result.optimization_space.sample()
    result.return_value = result
    result.objective_name = ""
    result.param_names = []
    result.constraint_names = []
    result.spec = Mock(
        id=f"MockEnv-{id(result)}-v0",
        entry_point=result,
        spec=gym.envs.registration.EnvSpec,
    )
    result.spec.make.return_value = result
    return result


@pytest.mark.parametrize("optimizer_factory_class", ALL_OPTIMIZERS.values())
def test_runner(
    mocker: MockerFixture,
    threadpool: QtCore.QThreadPool,
    optimizable: cernml.coi.SingleOptimizable,
    *,
    optimizer_factory_class: t.Type[OptimizerFactory],
) -> None:
    # Given:
    # TODO: It is no longer clear what the below line does. Uncomment it
    # in case problems appear, otherwise remove it in v0.4.0.
    # mocker.patch("numpy.clip", side_effect=lambda x, lower, upper: np.asanyarray(x))
    coi_make = mocker.patch("cernml.coi.make", return_value=optimizable)
    coi_spec = mocker.patch(
        "cernml.coi.spec", return_value=optimizable.spec  # type:ignore
    )
    recv = Mock()
    job_builder = OptJobBuilder()
    job_builder.problem_id = optimizable.spec.id  # type:ignore
    job_builder.optimizer_factory = optimizer_factory_class()
    # Ensure that ExtremumSeeking terminates.
    if hasattr(job_builder.optimizer_factory, "max_calls"):
        t.cast(t.Any, job_builder.optimizer_factory).max_calls = 10
    job_builder.signals.actors_updated.connect(recv.actors_updated)
    job_builder.signals.objective_updated.connect(recv.objective_updated)
    job_builder.signals.constraints_updated.connect(recv.constraints_updated)
    job_builder.signals.optimisation_finished.connect(recv.optimisation_finished)
    # When:
    threadpool.start(job_builder.build_job())
    threadpool.waitForDone()
    # Then:
    coi_make.assert_not_called()  # type:ignore
    coi_spec.assert_called_once_with(optimizable.spec.id)  # type:ignore
    optimizable.spec.make.assert_called_once_with()  # type:ignore
    optimizable.get_initial_params.assert_called_once_with()  # type:ignore
    steps = optimizable.compute_single_objective.call_count  # type:ignore
    assert steps >= 5
