import typing as t
from logging import getLogger
from pathlib import Path

import gym
from cernml.coi import cancellation
from gym.envs.registration import EnvSpec

from ...envs import make_env_by_name
from ..base import CannotBuildJob, Job, JobBuilder
from . import agents
from .wrapper import BenignCancelledError, RenderWrapper, Signals

if t.TYPE_CHECKING:
    from pyjapc import PyJapc  # pylint: disable=import-error, unused-import

LOG = getLogger(__name__)


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
        self._token_source = cancellation.TokenSource()
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
            self._env_id,
            make_japc=self._get_japc_or_raise,
            token=self._token_source.token,
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
            token_source=self._token_source,
            env=env,
            agent=agent,
            num_episodes=self.num_episodes,
            signals=self.signals,
        )


class ExecJob(Job):
    def __init__(
        self,
        *,
        token_source: cancellation.TokenSource,
        env: gym.Env,
        agent: agents.BaseAlgorithm,
        num_episodes: int,
        signals: Signals,
    ) -> None:
        super().__init__(token_source)
        self._signals = signals
        self._env = RenderWrapper(env, self._token_source.token, signals)
        self._num_episodes = num_episodes
        self._agent = agent
        self._finished = False

    def run(self) -> None:
        # pylint: disable = bare-except
        self._finished = False
        self._signals.new_run_started.emit()
        try:
            for _ in range(self._num_episodes):
                obs = self._env.reset()
                done = False
                state = None
                while not done:
                    action, state = self._agent.predict(obs, state)
                    obs, _, done, _ = self._env.step(action)
        except cancellation.CancelledError as exc:
            if isinstance(exc, BenignCancelledError):
                self._token_source.token.complete_cancellation()
            LOG.info("cancelled execution")
        except:
            LOG.error("aborted execution", exc_info=True)
        else:
            LOG.info("finished training")
        if self._token_source.can_reset_cancellation:
            self._token_source.reset_cancellation()
        self._signals.training_finished.emit(True)
        self._finished = True
