import typing as t
from dataclasses import dataclass

import gym
import numpy as np
from cernml.coi import cancellation
from cernml.mpl_utils import iter_matplotlib_figures
from PyQt5.QtCore import QObject, QThread, pyqtSignal


class BenignCancelledError(cancellation.CancelledError):
    """Cancellation error that we raise, not the :class:`SingleOptimizable`."""


@dataclass(frozen=True)
class PreRunMetadata:
    """Message object that provides information just before optimization.

    Attributes:
        objective_name: The physical meaning of the objective function,
            e.g. a device name.
        param_names: The physical meaning of each parameter, e.g. a
            device name.
    """

    Self = t.TypeVar("Self", bound="PreRunMetadata")

    objective_name: str
    param_names: t.Tuple[str, ...]

    @classmethod
    def from_env(cls: t.Type[Self], env: gym.Env) -> Self:
        """Create an instance based on the data in an environment."""
        num_actions = env.action_space.shape[0]
        return cls(
            objective_name="Reward",
            param_names=tuple(f"Action {i}" for i in range(1, 1 + num_actions)),
        )


class Signals(QObject):
    new_run_started = pyqtSignal(PreRunMetadata)
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
        return super().reset(**kwargs)

    def step(
        self, action: np.ndarray
    ) -> t.Tuple[np.ndarray, float, bool, t.Dict[str, t.Any]]:
        if self.cancellation_token.cancellation_requested:
            raise BenignCancelledError()
        obs, reward, done, info = super().step(action)
        episode_rewards = self.reward_lists[-1]
        episode_rewards.append(reward)
        self.episode_actions.append(np.array(action))
        # Send signals.
        xlist = np.arange(len(episode_rewards))
        self.signals.reward_lists_updated.emit(self.reward_lists)
        self.signals.objective_updated.emit(xlist, np.array(episode_rewards))
        self.signals.actors_updated.emit(xlist, np.array(self.episode_actions))
        self._render_env()
        return obs, reward, done, info

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
