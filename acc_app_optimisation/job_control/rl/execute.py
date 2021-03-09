import traceback
import typing as t
from logging import getLogger
from pathlib import Path

import gym
import numpy as np
from gym.envs.registration import EnvSpec
from PyQt5 import QtCore

from ...envs import make_env_by_name
from ..base import Job, JobBuilder
from . import agents

if t.TYPE_CHECKING:
    from io import BufferedIOBase  # pylint: disable=unused-import

    from pyjapc import PyJapc  # pylint: disable=import-error, unused-import

LOG = getLogger(__name__)


class CannotBuildJob(Exception):
    """One or more parameters is missing to build the job."""


class ExecutionCancelled(Exception):
    """The user clicked the Stop button to cancel execution."""


class Signals(QtCore.QObject):
    objective_updated = QtCore.pyqtSignal(np.ndarray, np.ndarray)
    actors_updated = QtCore.pyqtSignal(np.ndarray, np.ndarray)
    reward_lists_updated = QtCore.pyqtSignal(list)
    training_finished = QtCore.pyqtSignal(bool)


class ExecJobBuilder(JobBuilder):
    japc: t.Optional["PyJapc"]
    time_limit: int
    num_episodes: int
    agent_factory: t.Optional[agents.AgentFactory]
    agent_path: t.Optional[Path]
    signals: Signals

    def __init__(self) -> None:
        self._env: t.Optional[gym.Env] = None
        self._env_id = ""
        self.japc = None
        self.time_limit = 0
        self.num_episodes = 0
        self.agent_factory = None
        self.agent_path = None
        self.signals = Signals()

    @property
    def env_id(self) -> str:
        return self._env_id

    @env_id.setter
    def env_id(self, new_value: str) -> None:
        if new_value != self._env_id:
            self.unload_env()
        self._env_id = new_value

    @property
    def env(self) -> t.Optional[gym.Env]:
        return self._env

    def make_env(self) -> gym.Env:
        if not self._env_id:
            raise CannotBuildJob("no environment selected")
        self.unload_env()
        self._env = env = make_env_by_name(
            self._env_id, make_japc=self._get_japc_or_raise
        )
        spec: EnvSpec = env.spec  # type: ignore
        if spec.max_episode_steps is not None:
            LOG.debug("Default time limit: %d", spec.max_episode_steps)
            self.time_limit = spec.max_episode_steps
        else:
            LOG.debug("No default time limit")
            self.time_limit = 0
        return env

    def _get_japc_or_raise(self) -> "PyJapc":
        if self.japc is None:
            raise CannotBuildJob("no LSA context selected")
        LOG.debug("Using selector %s", self.japc.getSelector())
        return self.japc

    def unload_env(self) -> None:
        if self._env is not None:
            LOG.debug("Closing %s", self._env)
            self._env.close()
            self._env = None

    def build_job(self) -> "ExecJob":
        if self.agent_factory is None:
            raise CannotBuildJob("no algorithm selected")
        if self.agent_path is None:
            raise CannotBuildJob("no trained agent file selected")
        env = self._env if self._env is not None else self.make_env()
        if self.time_limit:
            env = gym.wrappers.TimeLimit(env, max_episode_steps=self.time_limit)
        agent = self.agent_factory.make_agent(env)
        agent = type(agent).load(self.agent_path)
        return ExecJob(
            env=env, agent=agent, num_episodes=self.num_episodes, signals=self.signals
        )


class ExecJob(Job):
    can_reset: t.ClassVar[bool] = False

    def __init__(
        self,
        env: gym.Env,
        agent: agents.BaseAlgorithm,
        num_episodes: int,
        signals: Signals,
    ) -> None:
        super().__init__()
        self._signals = signals
        self._env = RenderWrapper(env, signals)
        self._num_episodes = num_episodes
        self._agent = agent
        self._finished = False

    def run(self) -> None:
        # pylint: disable = bare-except
        self._finished = False
        try:
            for _ in range(self._num_episodes):
                obs = self._env.reset()
                done = False
                state = None
                while not done:
                    action, state = self._agent.predict(obs, state)
                    obs, _, done, _ = self._env.step(action)
        except ExecutionCancelled:
            LOG.info("Training cancelled")
        except:
            LOG.error(traceback.format_exc())
            LOG.error("Aborted training due to the above exception")
        else:
            LOG.info("Training finished")
        self._signals.training_finished.emit(True)
        self._finished = True

    def cancel(self) -> None:
        self._env.cancel()

    def save(self, path: t.Union[str, "Path", "BufferedIOBase"]) -> None:
        if not self._finished:
            raise RuntimeError("cannot save a model before or during training")
        self._agent.save(path)

    def reset(self) -> None:
        raise NotImplementedError("cannot reset training jobs")


class RenderWrapper(gym.Wrapper):
    def __init__(self, env: gym.Env, signals: Signals) -> None:
        self.episode_actions: t.List[np.ndarray] = []
        self.reward_lists: t.List[t.List[float]] = []
        self.signals = signals
        self._cancelled = False
        super().__init__(env)

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        self._cancelled = True

    def reset(self, **kwargs: t.Any) -> np.ndarray:
        if self._cancelled:
            raise ExecutionCancelled()
        self.reward_lists.append([])
        self.episode_actions.clear()
        return super().reset(**kwargs)

    def step(
        self, action: np.ndarray
    ) -> t.Tuple[np.ndarray, float, bool, t.Dict[str, t.Any]]:
        if self._cancelled:
            raise ExecutionCancelled()
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
