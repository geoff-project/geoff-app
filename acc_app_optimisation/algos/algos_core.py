from acc_app_optimisation.algos.algo_base import AlgoSingleBase
import gym
import numpy as np
import pybobyqa
from scipy.optimize import fmin_cobyla


class BobyQaAlgo(AlgoSingleBase):
    def __init__(self,env:gym.Env):
        super(AlgoSingleBase, self).__init__()
        self.env = env
        x_0 = env.get_initial_params()
        bounds_0 = (np.ones(env.optimization_space.shape[-1])*(-1.),np.ones(env.optimization_space.shape[-1])*1.)
        self.opt_params ={"x0":x_0,"bounds":bounds_0,"rhobeg":1.,"seek_global_minimum":False,"maxfun":100, "rhoend":0.05,"objfun_has_noise":False}
        self.opt_callback = lambda *args, **kwargs: pybobyqa.solve(*args, **kwargs).x


class CobylaAlgo(AlgoSingleBase):
    def constr1(self,x):
        return 1. -np.abs(x)

    def __init__(self,env:gym.Env):
        super(AlgoSingleBase, self).__init__()
        self.env = env
        x_0 = env.get_initial_params()
        bounds_0 = (np.ones(env.optimization_space.shape[-1])*(-1.),np.ones(env.optimization_space.shape[-1])*1.)
        self.opt_params ={"x0":x_0,"cons":[self.constr1],"rhobeg":1.,"maxfun":100, "rhoend":0.05}
        self.opt_callback = fmin_cobyla


all_single_algos_dict = {"BOBYQA":BobyQaAlgo,"COBYLA":CobylaAlgo}
