import typing as t

import gym
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

from ..base import CancellationToken


class Signals(QObject):
    objective_updated = pyqtSignal(np.ndarray, np.ndarray)
    actors_updated = pyqtSignal(np.ndarray, np.ndarray)
    reward_lists_updated = pyqtSignal(list)
    training_finished = pyqtSignal(bool)


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
        self, env: gym.Env, cancellation_token: CancellationToken, signals: Signals
    ) -> None:
        super().__init__(env)
        self.episode_actions: t.List[np.ndarray] = []
        self.reward_lists: t.List[t.List[float]] = []
        self.signals = signals
        self.cancellation_token = cancellation_token

    def reset(self, **kwargs: t.Any) -> np.ndarray:
        self.cancellation_token.raise_if_cancelled()
        self.reward_lists.append([])
        self.episode_actions.clear()
        return super().reset(**kwargs)

    def step(
        self, action: np.ndarray
    ) -> t.Tuple[np.ndarray, float, bool, t.Dict[str, t.Any]]:
        self.cancellation_token.raise_if_cancelled()
        obs, reward, done, info = super().step(action)
        episode_rewards = self.reward_lists[-1]
        episode_rewards.append(reward)
        self.episode_actions.append(np.array(action))
        # Send signals.
        xlist = np.arange(len(episode_rewards))
        self.signals.reward_lists_updated.emit(self.reward_lists)
        self.signals.objective_updated.emit(xlist, np.array(episode_rewards))
        self.signals.actors_updated.emit(xlist, np.array(self.episode_actions))
        return obs, reward, done, info
