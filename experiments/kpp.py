import numpy as np

from ophyd import EpicsSignal
from ophyd import EpicsSignalRO

from pcdsdevices.beam_stats import BeamEnergyRequest, BeamEnergyRequestACRWait

SET_WAIT = 2


class SettleSignal(EpicsSignal):
    def __init__(self, *args, settle_time=None, **kwargs):
        self._settle_time = settle_time
        super().__init__(*args, **kwargs)
    
    def set(self, *args, **kwargs):
        return super().set(*args, settle_time=self._settle_time, **kwargs)

class User():
    def __init__(self):
        self.energy_set = SettleSignal('XCS:USER:MCC:EPHOT:SET1', name='energy_set', settle_time=SET_WAIT)
        self.energy_ref = SettleSignal('XCS:USER:MCC:EPHOT:REF1', name='energy_ref')

        self.acr_energy = BeamEnergyRequestACRWait(name='acr_energy', prefix='XCS', acr_status_suffix='AO805') # AO801 for SXR
