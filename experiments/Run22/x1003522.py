import numpy as np
from hutch_python.utils import safe_load
from pcdsdevices import analog_signals
from xcs.db import daq, pp
from time import sleep
from ophyd import EpicsSignal
from ophyd import EpicsSignalRO
from ophyd import EpicsMotor

from pcdsdevices import analog_signals
#import pcdsdevices.analog_signals as analog_signals

SET_WAIT = 2


class SettleSignal(EpicsSignal):
    def __init__(self, *args, settle_time=None, **kwargs):
        self._settle_time = settle_time
        super().__init__(*args, **kwargs)
    
    def set(self, *args, **kwargs):
        return super().set(*args, settle_time=self._settle_time, **kwargs)

class User():
    def __init__(self):
        #with safe_load('analog_out'):
        self.aio = analog_signals.Acromag(name = 'xpp_aio', prefix = 'XPP:USR')
        self.dl = EpicsMotor(prefix='XPP:ENS:01:m0', name='aero')


    def move_yag(self):
        self.samx.umv(-7.0)
        self.samz.umv(0.8)
        self.diagx.umv(6)
        self.diagy.umv(1)
        self.diagz.umv(6)    
    
    def move_direct(self):
        self.samx.umv(-9)
        self.diagx.umv(6)
        self.diagy.umv(1)
        self.diagz.umv(6)    

    def move_silica(self):
        self.samx.umv(-9)
        self.diagx.umv(6)
        self.diagy.umv(1)
        self.diagz.umv(6)    

    def out_silica(self):
        self.diagy.umv(4)
        self.diagx.umv(-10)
        self.diagz.umv(-3)
