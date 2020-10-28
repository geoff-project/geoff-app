import gym
from PyQt5.QtCore import pyqtSignal, QObject, QRunnable, pyqtSlot
from numpy import ndarray
import numpy as np
from time import sleep

class AlgoSingleOptSignals(QObject):
    objetive_updated = pyqtSignal(ndarray, ndarray)
    optimisation_finished = pyqtSignal(bool)

class AlgoSingleBase(QRunnable):

    opt_params = {}
    opt_callback = None
    iteration_counter = 0
    iterations = []
    objectives = []
    signals = AlgoSingleOptSignals()


    def _env_callback(self,a):
        self.iteration_counter+=1
        self.iterations.append(self.iteration_counter)
        loss = self.env.compute_single_objective(a.copy())
        self.objectives.append(np.squeeze(loss))
        self.signals.objetive_updated.emit(np.array(self.iterations),np.array(self.objectives))
        return loss

    def solve(self):
        self.iteration_counter = 0
        self.iterations = []
        self.objectives = []
        optimum = self.opt_callback(self._env_callback,**self.opt_params)
        self._env_callback(optimum)
        self.signals.optimisation_finished.emit(True)

    def update_opt_param(self,keyword,value):
        if(keyword in self.opt_params):
            self.opt_params.update({keyword:value})

    @pyqtSlot()
    def run(self):
        self.solve()



