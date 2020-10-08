from gym import Env
import numpy as np
from gym import spaces
import acc_app_optimisation.algos.algos_core as algos
from time import sleep

class TestEnv(Env):
    def __init__(self):
        high = np.ones(1)
        low = (-1) * high
        self.action_space = spaces.Box(low=low, high=high, dtype=np.float32)
        self.action_scale = 10.

    def step(self, action):
        action = action *self.action_scale
        objective = action*action
        sleep(1)
        return None, objective,None,{}


    def reset(self):
        action = np.random.uniform(-1,1)
        action = action*self.action_scale
        return action

def print_evolution(x):
    print(x)

if __name__ == '__main__':
    env = TestEnv()


    boby = algos.all_single_algos_dict["BOBYQA"](env)

    boby.objetive_updated.connect(lambda x: print_evolution(x))

    result = boby.solve()




