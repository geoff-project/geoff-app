from acc_app_optimisation.algos.algo_base import AlgoSingleBase
import gym
import numpy as np
import pybobyqa


class BobyQaAlgo(AlgoSingleBase):
    def __init__(self, env: gym.Env):
        super(AlgoSingleBase, self).__init__()
        self.env = env
        x_0 = env.get_initial_params()
        bounds_0 = (
            np.ones(env.optimization_space.shape[-1]) * (-1.0),
            np.ones(env.optimization_space.shape[-1]) * 1.0,
        )
        self.opt_params = {
            "x0": x_0,
            "bounds": bounds_0,
            "rhobeg": 1.0,
            "seek_global_minimum": False,
            "maxfun": 100,
            "rhoend": 0.1,
            "objfun_has_noise": False,
        }
        self.opt_callback = pybobyqa.solve


all_single_algos_dict = {"BOBYQA": BobyQaAlgo}
