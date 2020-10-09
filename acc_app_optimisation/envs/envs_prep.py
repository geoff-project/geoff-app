from cernml import coi
import cern_awake_env.simulation
import cern_awake_env.machine

class AllEnvs():

    accelerator = None

    def setAccelerator(self,accelerator):
        self.accelerator = accelerator

    def getAllEnvsForAccelerator(self):
        env_names = [
            spec.id
            for spec in coi.registry.all()
            if spec.entry_point.metadata['cern.machine'].value == self.accelerator.acc_name
        ]
        return env_names

    def getSelectedEnv(self, name, japc):
        spec = coi.registry.spec(name)
        needs_japc = spec.entry_point.metadata['cern.japc']
        if needs_japc:
            env = coi.make(name, japc=japc)
        else:
            env = coi.make(name)
        return env