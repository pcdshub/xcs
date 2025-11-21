import numpy as np
import matplotlib.pyplot as plt
import lmfit 
from hutch_python.utils import safe_load
from pcdsdevices import analog_signals
from xcs.db import daq, pp, RE, bp
from xcs.db import xcs_gon as gon
from xcs.db import xcs_attenuator as att
from time import sleep
from ophyd import EpicsSignal
from ophyd import EpicsSignalRO
from ophyd import EpicsMotor
from time import sleep
from pcdsdevices import analog_signals
from pcdsdevices.device_types import IMS
from bluesky.callbacks import LiveFit
from bluesky.callbacks.mpl_plotting import LivePlot, LiveFitPlot


beamstop = IMS('XCS:LAM:MMS:12', name='bs6_r')

SET_WAIT = 2


class SettleSignal(EpicsSignal):
    def __init__(self, *args, settle_time=None, **kwargs):
        self._settle_time = settle_time
        super().__init__(*args, **kwargs)
    
    def set(self, *args, **kwargs):
        return super().set(*args, settle_time=self._settle_time, **kwargs)

def gaussian(x, A, sigma, x0):
    return A*np.exp(-(x - x0)**2/(2 * sigma**2))

class User():
    """Generic User Object"""
    with safe_load('Dummy'):
#        gon_2th=gon.rot_2theta
        print('Import dummy')
#    beamstop = beamstop

    def __init__(self):
        #with safe_load('analog_out'):

        #with safe_load('analog_out'):
        self.aio = analog_signals.Acromag(name = 'xcs_aio', prefix = 'XCS:USR')

    def move_yag(self):
        att(1e-3)
        sleep(2)
        self.samx.umv_yag()
        self.samy.umv_yag()
        self.samz.umv_yag()
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

#    def dscan_gaussian(self, det,motor, start, end, nsteps, nEvents, records=None):
#        model = lmfit.Model(gaussian)
#        init_guess = {'A': 2,'sigma': lmfit.Parameter('sigma', 3, min=0),'x0': 21.2}
#        fig,ax = plt.subplots()
#        print(motor)
#        detname=det.name+'_mean'
#        lf = LiveFit(model, detname, {'x': motor}, init_guess)
#        fig, ax = plt.subplots() 
#        lfp = LiveFitPlot(lf, ax=ax, color='r')
#        lp = LivePlot(detname, motor, ax=ax, marker='o', linestyle='none')
#        RE(bp.daq_ascan([det], motor,start,end,nsteps,events=nEvents,record=records ),[lp,lfp])
#        print(lf.result.values)







