import numpy as np
from hutch_python.utils import safe_load
from pcdsdevices import analog_signals
from xcs.db import daq, pp
from xcs.db import xcs_gon as gon
from xcs.db import xcs_attenuator as att
from time import sleep
from ophyd import EpicsSignal
from ophyd import EpicsSignalRO
from ophyd import EpicsMotor
from time import sleep
from pcdsdevices import analog_signals
from pcdsdevices.device_types import IMS

beamstop = IMS('XCS:LAM:MMS:12', name='bs6_r')

#import pcdsdevices.analog_signals as analog_signals

SET_WAIT = 2


class SettleSignal(EpicsSignal):
    def __init__(self, *args, settle_time=None, **kwargs):
        self._settle_time = settle_time
        super().__init__(*args, **kwargs)
    
    def set(self, *args, **kwargs):
        return super().set(*args, settle_time=self._settle_time, **kwargs)

class User():
    """Generic User Object"""
    with safe_load('Dummy'):
        gon_2th=gon.rot_2theta
        print('Import dummy')
    beamstop = beamstop

    def __init__(self):
        #with safe_load('analog_out'):

        #with safe_load('analog_out'):
        self.aio = analog_signals.Acromag(name = 'xcs_aio', prefix = 'XCS:USR')


    def move_gontth(self,tth=5,z_offset=150,det_position=690):
        """ move the gon 2th with z_offset """
        target_tth = np.rad2deg(np.arctan(((det_position-z_offset)*np.tan(np.deg2rad(tth)))/det_position))
        self.gon_2th.umv(target_tth)
        print(target_tth)
   
    def move_yag(self):
        att(1e-3)
        sleep(2)
        self.samx.umv_yag()
        self.samy.umv_yag()
        self.samz.umv_yag()
#        self.samth.umv_yag()
        self.diagy.umv(11.4)
        att(1e-1)

    def move_s1(self):
        att(1e-3)
        sleep(2)
        self.samx.umv_s1()
        self.samy.umv_s1()
        self.samz.umv_s1()
        self.samth.umv_s1()
        self.diagy.umv(11.4)
        att(0.05)    

    def move_silica(self):
        att(1e-3)
        sleep(2)
        self.samx.umv_yag()
        self.samy.umv_yag()
        self.samy.umvr(-1)
        self.samz.umv_yag()
        self.samth.umv_yag()
        self.diagy.umv(11.4-4)
        att(1e-1)

    def takeRun(self, nEvents, record=None, use_l3t=False):
        daq.configure(events=120, record=record, use_l3t=use_l3t)
        daq.begin(events=nEvents)
        daq.wait()
        daq.end_run()



