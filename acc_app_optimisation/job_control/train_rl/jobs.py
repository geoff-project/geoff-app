import traceback
import typing as t
from logging import getLogger

import gym
import numpy as np
from cernml import coi
from PyQt5 import QtCore

from ..base import Job, JobBuilder
from . import agents

if t.TYPE_CHECKING:
    from io import BufferedIOBase  # pylint: disable=unused-import
    from pathlib import Path  # pylint: disable=unused-import

    from pyjapc import PyJapc  # pylint: disable=import-error, unused-import

LOG = getLogger(__name__)


class CannotBuildJob(Exception):
    """One or more parameters is missing to build the job."""


class TrainingCancelled(Exception):
    """The user clicked the Stop button to cancel training."""


class Signals(QtCore.QObject):
    step_finished = QtCore.pyqtSignal(list)
    training_finished = QtCore.pyqtSignal(bool)


class TrainJobBuilder(JobBuilder):
    japc: t.Optional["PyJapc"]
    agent_factory: t.Optional[agents.AgentFactory]
    signals: Signals

    def __init__(self) -> None:
        self._env: t.Optional[gym.Env] = None
        self._env_id = ""
        self.japc = None
        self.agent_factory = None
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
        spec = coi.spec(self._env_id)
        needs_japc = spec.entry_point.metadata.get("cern.japc", False)
        kwargs: t.Dict[str, t.Any] = {}
        if needs_japc:
            if self.japc is None:
                raise CannotBuildJob("no LSA context selected")
            LOG.debug("Using selector %s", self.japc.getSelector())
            kwargs["japc"] = self.japc
        else:
            LOG.debug("Using no JAPC")
        LOG.debug("Making %s", self._env_id)
        self._env = env = coi.make(self._env_id, **kwargs)
        return env

    def unload_env(self) -> None:
        if self._env is not None:
            LOG.debug("Closing %s", self._env)
            self._env.close()
            self._env = None

    def build_job(self) -> "TrainJob":
        if self.agent_factory is None:
            raise CannotBuildJob("no algorithm selected")
        env = self._env if self._env is not None else self.make_env()
        return TrainJob(env=env, agent_factory=self.agent_factory, signals=self.signals)


class TrainJob(Job):
    can_reset: t.ClassVar[bool] = False

    def __init__(
        self, env: gym.Env, agent_factory: agents.AgentFactory, signals: Signals
    ) -> None:
        super().__init__()
        self._signals = signals
        self._env = RenderWrapper(env, signals)
        self._total_timesteps = agent_factory.total_timesteps
        self._agent = agent_factory.make_agent(self._env)
        self._finished = False

    def run(self) -> None:
        # pylint: disable = bare-except
        self._finished = False
        try:
            self._agent.learn(self._total_timesteps)
        except TrainingCancelled:
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
            raise TrainingCancelled()
        self.reward_lists.append([])
        return super().reset(**kwargs)

    def step(
        self, action: np.ndarray
    ) -> t.Tuple[np.ndarray, float, bool, t.Dict[str, t.Any]]:
        if self._cancelled:
            raise TrainingCancelled()
        obs, reward, done, info = super().step(action)
        self.reward_lists[-1].append(reward)
        self.signals.step_finished.emit(self.reward_lists)
        return obs, reward, done, info
