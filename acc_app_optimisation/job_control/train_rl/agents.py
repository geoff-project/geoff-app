import abc
import typing as t
from types import SimpleNamespace

import gym
import numpy as np
import stable_baselines3 as sb3
from cernml import coi
from stable_baselines3.common.base_class import BaseAlgorithm


class AgentFactory(coi.Configurable, metaclass=abc.ABCMeta):
    total_timesteps: int

    def __init__(self) -> None:
        self.total_timesteps = 300

    def get_config(self) -> coi.Config:
        config = coi.Config()
        config.add("total_timesteps", self.total_timesteps, range=(0, np.inf))
        return config

    def apply_config(self, values: SimpleNamespace) -> None:
        self.total_timesteps = values.total_timesteps

    @abc.abstractmethod
    def make_agent(self, env: gym.Env) -> BaseAlgorithm:
        pass


class TD3(AgentFactory):
    def __init__(self) -> None:
        super().__init__()
        self.learning_starts = 100
        self.action_noise = 0.1

    def get_config(self) -> coi.Config:
        config = super().get_config()
        config.add("learning_starts", self.learning_starts, range=(0, np.inf))
        config.add("action_noise", self.action_noise, range=(0.0, 1.0))
        return config

    def apply_config(self, values: SimpleNamespace) -> None:
        if not values.learning_starts < values.total_timesteps:
            raise coi.BadConfig(
                f"bad learning_starts: expected less than "
                f"{self.total_timesteps}, got {values.learning_starts}"
            )
        super().apply_config(values)
        self.learning_starts = values.learning_starts
        self.action_noise = values.action_noise

    def make_agent(self, env: gym.Env) -> BaseAlgorithm:
        assert isinstance(env.action_space, gym.spaces.Box), env.action_space
        return sb3.TD3(
            "MlpPolicy",
            env,
            learning_starts=self.learning_starts,
            action_noise=self._make_action_noise(env.action_space),
            verbose=1,
        )

    def _make_action_noise(
        self, ac_space: gym.spaces.Box
    ) -> t.Optional[sb3.common.noise.ActionNoise]:
        if self.action_noise:
            return sb3.common.noise.NormalActionNoise(
                mean=np.zeros(ac_space.shape),
                sigma=self.action_noise * np.ones(ac_space.shape),
            )
        return None


ALL_AGENTS: t.Mapping[str, t.Type[AgentFactory]] = {
    "TD3": TD3,
}
