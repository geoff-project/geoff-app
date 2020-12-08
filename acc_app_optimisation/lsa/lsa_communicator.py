import pjlsa

lsa = pjlsa.LSAClient(server="next")

import jpype.imports
jpype.imports.registerDomain("cern")

from cern.lsa.client import (
    ServiceLocator,
    ContextService,
    ParameterService,
    SettingService,
    TrimService
)
from cern.lsa.domain.settings import ContextSettingsRequest, Settings, IncorporationRequest, IncorporationSetting
from cern.lsa.domain.settings import Contexts
from cern.lsa.domain.settings.spi import ScalarSetting
from cern.accsoft.commons.value import Type
from java.util import Collections
from cern.accsoft.commons.value import ValueFactory


class LSACommunicator:
    context_service = ServiceLocator.getService(ContextService)
    parameter_service = ServiceLocator.getService(ParameterService)
    setting_service = ServiceLocator.getService(SettingService)
    trim_service = ServiceLocator.getService(TrimService)

    def get_parameter_setting(self,
                              parameter: str = "QF/IREF",
                              context: str = "SFT_PRO_MTE_L4780_2018_V1"):
        parameter = self.parameter_service.findParameterByName(parameter)
        cycle = self.context_service.findStandAloneCycle(context)
        cycle_settings = self.setting_service.findContextSettings(
            ContextSettingsRequest.byStandAloneContextAndParameters(
                cycle,
                Collections.singleton(parameter),
            ))
        function = Settings.getFunction(cycle_settings, parameter)
        function_times = function.toXArray()
        function_values = function.toYArray()
        return function_times, function_values

    def incorporate_setting(self,
                            parameter_name: str,
                            context: str,
                            delta_setting: float,
                            time: float):
        cycle = self.context_service.findStandAloneCycle(context)
        parameter = self.parameter_service.findParameterByName(parameter_name)

        scalar_setting = ScalarSetting(Type.DOUBLE)
        beamProcess = Contexts.getFunctionBeamProcessAt(cycle, parameter.getParticleTransfers().iterator().next(), time)
        scalar_setting.setBeamProcess(beamProcess)
        beamProcess_startTime = beamProcess.getStartTime()
        time_for_incoroporation = time-beamProcess_startTime
        scalar_setting.setParameter(parameter)
        scalar_setting.setTargetValue(ValueFactory.createScalar(0.0))
        scalar_setting.setCorrectionValue(ValueFactory.createScalar(delta_setting))

        incorporation_request = IncorporationRequest.builder().\
            setContext(cycle).\
            setRelative(True).\
            addIncorporationSetting(IncorporationSetting(scalar_setting, time_for_incoroporation)).\
            build()

        self.trim_service.incorporate(incorporation_request)

if __name__ == "__main__":
    communicator = LSACommunicator()

    context = "HIRADMAT_PILOT_Q20_2018_V1"
    parameter_name = "logical.RDH.20207/K"
    time=2305.
    delta_setting=5e-6
    communicator.incorporate_setting(context=context,parameter_name=parameter_name,time=time,delta_setting=delta_setting)


