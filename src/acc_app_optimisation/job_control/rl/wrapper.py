# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

import sys
import traceback
import typing as t
from dataclasses import dataclass

import gymnasium as gym
import numpy as np
from cernml.coi import cancellation
from cernml.mpl_utils import iter_matplotlib_figures
from PyQt5.QtCore import QObject, QThread, pyqtSignal

if sys.version_info < (3, 10):
    from typing_extensions import Self
else:
    from typing import Self


class BenignCancelledError(cancellation.CancelledError):
    """Cancellation error that we raise, not the :class:`SingleOptimizable`."""


@dataclass(frozen=True)
class PreRunMetadata:
    """Message object that provides information just before optimization.

    Attributes:
        env_id: The registered name of the environment that is being
            optimized.
        objective_name: The physical meaning of the objective function,
            e.g. a device name.
        param_names: The physical meaning of each parameter, e.g. a
            device name.
        time_limit: A parameter configured on the environment that
            limits the number of steps per episode. `None` if there is
            no limit or no limit could be found (e.g. because it isn't
            specified in the `~gym.envs.registration.EnvSpec`).
        total_timesteps: A parameter configured on the
            RL agent that limits the number of steps performed on the
            environment. `None` if there is no limit or no limit could
            be found (e.g. because the agent is not part of Stable
            Baselines and GeOFF does not know the parameter's name).
    """

    env_id: str
    objective_name: str
    param_names: t.Tuple[str, ...]
    time_limit: t.Optional[int]
    total_timesteps: t.Optional[int]

    @classmethod
    def from_env(
        cls, env: gym.Env, env_id: str, total_timesteps: t.Optional[int]
    ) -> Self:
        """Create an instance based on the data in an environment."""
        num_actions = env.action_space.shape[0]
        return cls(
            env_id=env_id,
            objective_name="Reward",
            param_names=tuple(f"Action {i}" for i in range(1, 1 + num_actions)),
            time_limit=env.spec.max_episode_steps if env.spec is not None else None,
            total_timesteps=total_timesteps,
        )


class Signals(QObject):
    """Signals emitted by `OptJob`.

    Attributes:
        new_run_started:
            Emitted just before training or execution start. In
            particular this is emitted before the first call to
            `~gym.Env.reset()`.
        new_episode_started:
            Emitted before calling `~gym.Env.reset()`.
        step_started:
            Emitted before calling `~gym.Env.step()`.
        reward_lists_updated:
            Emitted at the end of `~gym.Env.step()`. The argument is a
            list of the final rewards per episode. Always has at least
            one entry. The last entry of the list keeps changing until
            the episode has finished.
        objective_updated:
            Emitted at the end of `~gym.Env.step()`, together with
            *reward_lists_updated*. First argument is an array of shape
            :math:`(N,)` with all step indices of the current episode as
            X coordinates, second parameter is an array of the same
            shape with the rewards returned at each step.
        actors_updated:
            Emitted at the end of `~gym.Env.step()`, together with
            *reward_lists_updated*. First argument is an array of shape
            :math:`(N,)` with all step indices of the current episode as
            X coordinates, second parameter is a 2D array of shape
            :math:`(N, A)` shape with the actions chosen at each step.
        run_finished:
            Emitted at the end of training or execution. The Boolean
            argument is True if the algorithm ran until completion,
            False if it was cancelled by the user.
        run_failed:
            Emitted after training or execution ended irregularly
            through an exception *other than*
            `cernml.coi.cancellation.CancelledError`.
    """

    new_run_started = pyqtSignal(PreRunMetadata)
    new_episode_started = pyqtSignal()
    step_started = pyqtSignal()
    reward_lists_updated = pyqtSignal(list)
    objective_updated = pyqtSignal(np.ndarray, np.ndarray)
    actors_updated = pyqtSignal(np.ndarray, np.ndarray)
    run_finished = pyqtSignal(bool)
    run_failed = pyqtSignal(traceback.TracebackException)


class RenderWrapper(gym.Wrapper):
    """Environment wrapper that communicates with the GUI on each step.

    Args:
        env: The environment to wrap.
        cancellation_token: The cancellation token of the
            :py:class:`Job` that uses this wrapper. Its status is
            checked on each :py:meth:`reset()` and :py:meth:`step()`
            call to ensure that loops on this environment can be
            cancelled.
        signals: A collection of signals that are emitted on each
            :py:meth:`step()` call.
    """

    def __init__(
        self, env: gym.Env, cancellation_token: "cancellation.Token", signals: Signals
    ) -> None:
        super().__init__(env)
        self.episode_actions: t.List[np.ndarray] = []
        self.reward_lists: t.List[t.List[float]] = []
        self.signals = signals
        self.cancellation_token = cancellation_token

    def reset(self, **kwargs: t.Any) -> np.ndarray:
        self.cancellation_token.raise_if_cancellation_requested()
        self.reward_lists.append([])
        self.episode_actions.clear()
        self.signals.new_episode_started.emit()
        return super().reset(**kwargs)

    def step(
        self, action: np.ndarray
    ) -> t.Tuple[np.ndarray, float, bool, bool, t.Dict[str, t.Any]]:
        if self.cancellation_token.cancellation_requested:
            raise BenignCancelledError()
        self.signals.step_started.emit()
        obs, reward, terminated, truncated, info = super().step(action)
        episode_rewards = self.reward_lists[-1]
        episode_rewards.append(reward)
        self.episode_actions.append(np.array(action))
        # Send signals.
        xlist = np.arange(len(episode_rewards))
        self.signals.reward_lists_updated.emit(self.reward_lists)
        self.signals.objective_updated.emit(xlist, np.array(episode_rewards))
        self.signals.actors_updated.emit(xlist, np.array(self.episode_actions))
        self._render_env()
        return obs, reward, terminated, truncated, info

    def _render_env(self) -> None:
        if "matplotlib_figures" not in self.metadata.get("render.modes", []):
            return
        figures = self.render("matplotlib_figures")
        # `draw()` refreshes the figures immediately on this thread. Do
        # not use `draw_idle()`: it postpones drawing until the next
        # time the (main thread) event loop runs. This leads to a race
        # condition between the main thread drawing the figures and this
        # thread modifying them.
        for _, figure in iter_matplotlib_figures(figures):
            QThread.yieldCurrentThread()
            figure.canvas.draw()
