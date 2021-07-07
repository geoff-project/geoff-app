import abc
import inspect
import typing as t
from types import SimpleNamespace

import gym
import numpy as np
import stable_baselines3 as sb3
from cernml import coi
from cernml.svd import SvdOptimizer
from stable_baselines3.common.base_class import BaseAlgorithm

# Mark SvdOptimizer as a virtual subclass of BaseAlgorithm.
BaseAlgorithm.register(SvdOptimizer)


class AgentFactory(coi.Configurable, metaclass=abc.ABCMeta):
    total_timesteps: int

    def __init__(self) -> None:
        self.total_timesteps = 300

    def get_config(self) -> coi.Config:
        config = coi.Config()
        config.add(
            "total_timesteps",
            self.total_timesteps,
            range=(0, np.inf),
            label="Total time steps",
            help="Duration of training in number of steps on the environment",
        )
        return config

    def apply_config(self, values: SimpleNamespace) -> None:
        self.total_timesteps = values.total_timesteps

    @abc.abstractmethod
    def make_agent(self, env: gym.Env) -> BaseAlgorithm:
        pass


class TD3(AgentFactory):
    def __init__(self) -> None:
        super().__init__()
        defaults = _get_default_args(sb3.TD3)
        self.buffer_size: int = defaults["buffer_size"]
        self.learning_starts: int = defaults["learning_starts"]
        self.learning_rate: float = defaults["learning_rate"]
        self.gamma: float = defaults["gamma"]
        self.tau: float = defaults["tau"]
        self.action_noise: float = 0.1

    def get_config(self) -> coi.Config:
        config = super().get_config()
        config.add(
            "learning_starts",
            self.learning_starts,
            range=(0, np.inf),
            label="Learning starts",
            help="Number of steps in the initial exploration phase",
        )
        config.add(
            "buffer_size",
            self.buffer_size,
            range=(10, np.inf),
            label="Buffer size",
            help="Size of the replay buffer",
        )
        config.add(
            "gamma",
            self.gamma,
            range=(0.0, 1.0),
            label="Discount factor",
            help="Lower values make the agent more short-sighted",
        )
        config.add(
            "tau",
            self.tau,
            range=(0.0, 1.0),
            label="Polyak update coefficient",
            help="Higher values reduce the delay between main and target Q network",
        )
        config.add(
            "action_noise",
            self.action_noise,
            range=(0.0, 1.0),
            label="Action noise scale",
            help="Amount of Gaussian noise to add on actions during training",
        )
        config.add(
            "learning_rate",
            self.learning_rate,
            range=(1e-10, 1e0),
            label="Learning rate",
            help="Update step size during learning",
        )
        return config

    def apply_config(self, values: SimpleNamespace) -> None:
        if not values.learning_starts < values.total_timesteps:
            raise coi.BadConfig(
                f"bad learning_starts: expected less than "
                f"{self.total_timesteps}, got {values.learning_starts}"
            )
        super().apply_config(values)
        self.learning_starts = values.learning_starts
        self.buffer_size = values.buffer_size
        self.learning_rate = values.learning_rate
        self.gamma = values.gamma
        self.tau = values.tau
        self.action_noise = values.action_noise

    def make_agent(self, env: gym.Env) -> BaseAlgorithm:
        assert isinstance(env.action_space, gym.spaces.Box), env.action_space
        return sb3.TD3(
            "MlpPolicy",
            env,
            learning_starts=self.learning_starts,
            buffer_size=self.buffer_size,
            learning_rate=self.learning_rate,
            gamma=self.gamma,
            tau=self.tau,
            action_noise=_make_action_noise(env.action_space, self.action_noise),
            verbose=1,
        )


class SAC(AgentFactory):
    def __init__(self) -> None:
        super().__init__()
        defaults = _get_default_args(sb3.SAC)
        self.buffer_size: int = defaults["buffer_size"]
        self.learning_starts: int = defaults["learning_starts"]
        self.learning_rate: float = defaults["learning_rate"]
        self.gamma: float = defaults["gamma"]
        self.tau: float = defaults["tau"]
        self.action_noise: float = 0.1

    def get_config(self) -> coi.Config:
        config = super().get_config()
        config.add(
            "learning_starts",
            self.learning_starts,
            range=(0, np.inf),
            label="Learning starts",
            help="Number of steps in the initial exploration phase",
        )
        config.add(
            "buffer_size",
            self.buffer_size,
            range=(10, np.inf),
            label="Buffer size",
            help="Size of the replay buffer",
        )
        config.add(
            "gamma",
            self.gamma,
            range=(0.0, 1.0),
            label="Discount factor",
            help="Lower values make the agent more short-sighted",
        )
        config.add(
            "tau",
            self.tau,
            range=(0.0, 1.0),
            label="Polyak update coefficient",
            help="Higher values reduce the delay between main and target Q network",
        )
        config.add(
            "action_noise",
            self.action_noise,
            range=(0.0, 1.0),
            label="Action noise scale",
            help="Amount of Gaussian noise to add on actions during training",
        )
        config.add(
            "learning_rate",
            self.learning_rate,
            range=(1e-10, 1e0),
            label="Learning rate",
            help="Update step size during learning",
        )
        return config

    def apply_config(self, values: SimpleNamespace) -> None:
        if not values.learning_starts < values.total_timesteps:
            raise coi.BadConfig(
                f"bad learning_starts: expected less than "
                f"{self.total_timesteps}, got {values.learning_starts}"
            )
        super().apply_config(values)
        self.learning_starts = values.learning_starts
        self.buffer_size = values.buffer_size
        self.learning_rate = values.learning_rate
        self.gamma = values.gamma
        self.tau = values.tau
        self.action_noise = values.action_noise

    def make_agent(self, env: gym.Env) -> BaseAlgorithm:
        assert isinstance(env.action_space, gym.spaces.Box), env.action_space
        return sb3.SAC(
            "MlpPolicy",
            env,
            learning_starts=self.learning_starts,
            buffer_size=self.buffer_size,
            learning_rate=self.learning_rate,
            gamma=self.gamma,
            tau=self.tau,
            action_noise=_make_action_noise(env.action_space, self.action_noise),
            verbose=1,
        )


class SVD(AgentFactory):
    def __init__(self) -> None:
        super().__init__()
        defaults = _get_default_args(SvdOptimizer)
        self.action_scale: float = defaults["action_scale"]
        self.max_action_size: float = defaults["max_action_size"]
        self.verbose: bool = defaults["verbose"]

    def get_config(self) -> coi.Config:
        config = super().get_config()
        config.add(
            "action_scale",
            self.action_scale,
            range=(0, np.inf),
            label="Training step size",
            help="Size of the steps to take during training",
        )
        config.add(
            "max_action_size",
            self.max_action_size,
            range=(0, np.inf),
            label="Maximum prediction step size",
            help="Limit on the step size during evaluation",
        )
        config.add(
            "verbose",
            self.verbose,
            type=bool,
            label="Verbose output",
            help="Enable to produce more logging output",
        )
        return config

    def apply_config(self, values: SimpleNamespace) -> None:
        super().apply_config(values)
        self.action_scale = values.action_scale
        self.max_action_size = values.max_action_size
        self.verbose = values.verbose

    def make_agent(self, env: gym.Env) -> BaseAlgorithm:
        agent = SvdOptimizer(
            env,
            action_scale=self.action_scale,
            max_action_size=self.max_action_size,
            verbose=self.verbose,
        )
        # This is fine – we've registered SvdOptimizer as a subclass of
        # the ABC BaseAlgorithm and it fulfills enough of the API.
        return t.cast(BaseAlgorithm, agent)


ALL_AGENTS: t.Mapping[str, t.Type[AgentFactory]] = {
    "TD3": TD3,
    "SAC": SAC,
    "SVD": SVD,
}


def _get_default_args(func: t.Callable) -> t.Dict[str, t.Any]:
    signature = inspect.signature(func)
    return {
        name: param.default
        for name, param in signature.parameters.items()
        if param.default is not param.empty and not name.startswith("_")
    }


def _make_action_noise(
    ac_space: gym.spaces.Box,
    scale: float,
) -> t.Optional[sb3.common.noise.ActionNoise]:
    if scale:
        return sb3.common.noise.NormalActionNoise(
            mean=np.zeros(ac_space.shape),
            sigma=np.ones(ac_space.shape) * scale,
        )
    return None
