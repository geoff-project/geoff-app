# SPDX-FileCopyrightText: 2020-2023 CERN
# SPDX-FileCopyrightText: 2023 GSI Helmholtzzentrum für Schwerionenforschung
# SPDX-FileNotice: All rights not expressly granted are reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later OR EUPL-1.2+

import typing as t
from logging import getLogger

import gym
from cernml import coi
from cernml.coi.cancellation import TokenSource as CancellationTokenSource
from gym.envs.registration import EnvSpec

from ...envs import make_env_by_name
from ..base import CannotBuildJob, Job, JobBuilder, catching_exceptions
from .agents import GenericAgentFactory
from .wrapper import PreRunMetadata, RenderWrapper, Signals

if t.TYPE_CHECKING:
    from pyjapc import PyJapc  # pylint: disable=import-error, unused-import

LOG = getLogger(__name__)


class ExecJobBuilder(JobBuilder):
    japc: t.Optional["PyJapc"]
    """The PyJapc instance to pass to the environment. If None, nothing
    is passed."""
    time_limit: int
    """Envs always run in a time limit."""
    num_episodes: int
    """The number of episodes to run."""
    policy_provider: t.Optional[coi.CustomPolicyProvider]
    """The policy provider. The default is a generic policy provider
    that loads its algorithm weights from a user-specified ZIP file. If
    None, the *actual* policy provider is the env itself."""
    policy_name: str
    """The name of the policy. To be passed to the policy provider. If
    the empty string, no policy has been selected yet and we cannot
    start a job."""
    signals: Signals
    """Qt signals that the outside world can connect to."""

    def __init__(self) -> None:
        self._env: t.Optional[gym.Env] = None
        self._env_id = ""
        self._token_source = CancellationTokenSource()
        self.japc = None
        self.time_limit = 0
        self.num_episodes = 0
        self.policy_provider = GenericAgentFactory()
        self.policy_name = ""
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
        if not self.policy_name:
            raise CannotBuildJob("no algorithm selected")
        env = self._env if self._env is not None else self.make_env()
        if self.time_limit:
            env = gym.wrappers.TimeLimit(env, max_episode_steps=self.time_limit)
        provider = self.policy_provider or env
        policy = provider.load_policy(self.policy_name)
        return ExecJob(
            token_source=self._token_source,
            env=env,
            policy=policy,
            num_episodes=self.num_episodes,
            signals=self.signals,
        )


class ExecJob(Job):
    def __init__(
        self,
        *,
        token_source: CancellationTokenSource,
        env: gym.Env,
        policy: coi.Policy,
        num_episodes: int,
        signals: Signals,
    ) -> None:
        super().__init__(token_source)
        self._signals = signals
        self._env = RenderWrapper(env, self._token_source.token, signals)
        self._num_episodes = num_episodes
        self._policy = policy

    @property
    def env_id(self) -> str:
        """The name of the environment."""
        env = self._env.unwrapped
        spec = getattr(env, "spec", None)
        if spec:
            return spec.id
        env_class = type(env)
        return ".".join([env_class.__module__, env_class.__qualname__])

    def run(self) -> None:
        # pylint: disable = bare-except
        LOG.info(
            "start execution of %s in env %s", type(self._policy).__name__, self.env_id
        )
        self._signals.new_run_started.emit(
            PreRunMetadata.from_env(self._env, self.env_id, total_timesteps=None)
        )
        with catching_exceptions(
            "execution",
            LOG,
            token_source=self._token_source,
            on_success=lambda: self._signals.run_finished.emit(True),
            on_cancel=lambda: self._signals.run_finished.emit(False),
            on_exception=self._signals.run_failed.emit,
        ):
            for i in range(1, 1 + self._num_episodes):
                LOG.info("episode %d/%d", i, self._num_episodes)
                obs = self._env.reset()
                done = False
                state = None
                while not done:
                    action, state = self._policy.predict(obs, state, deterministic=True)
                    obs, _, done, _ = self._env.step(action)
