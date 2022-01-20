from subprocess import check_output

import logging
import json
import sys
import time
import os

import numpy as np
from hutch_python.utils import safe_load
from ophyd import EpicsSignalRO
from ophyd import EpicsSignal
from bluesky import RunEngine
from bluesky.plans import scan
from bluesky.plans import list_scan
from ophyd import Component as Cpt
from ophyd import Device
from pcdsdevices.interface import BaseInterface
from pcdsdevices.areadetector import plugins
from xcs.db import daq
from xcs.db import camviewer
from xcs.db import RE
from xcs.db import xcs_ccm as ccm
from xcs.delay_scan import delay_scan
from xcs.db import lxt_fast
from pcdsdevices.device_types import Newport, IMS

#from macros import *
import time

logger = logging.getLogger(__name__)

class User():
    def __init__(self):
        pass
    
        #with safe_load('lv3718_motors'):
            #self.JF_y = IMS('XCS:USR:MMS:33', name='JF_y')
            #self.zyla_x = IMS('XCS:USR:MMS:34', name='zyla_x')
            #self.sam_y = IMS('XCS:USR:MMS:35', name='sam_y')
            #self.zyla_z = IMS('XCS:USR:MMS:36', name='zyla_z')
            #self.mirror_x = IMS('XCS:USR:MMS:41', name='mirror_x')
            #self.mirror_y = IMS('XCS:USR:MMS:48', name='mirror_y')
            #self.zyla_z = IMS('XCS:USR:MMS:44', name='zyla_z')
            #self.zyla_y = IMS('XCS:USR:MMS:43', name='zyla_y')
            #self.sam_th = IMS('XCS:USR:MMS:45', name='sam_th')
            #self.jj2hg = IMS('XCS:USR:MMS:25', name='jj2hg')
            #self.jj2ho = IMS('XCS:USR:MMS:26', name='jj2ho')
            #self.jj2vg = IMS('XCS:USR:MMS:27', name='jj2vg')
            #self.jj2vo = IMS('XCS:USR:MMS:28', name='jj2vo')
            #self.samyag_z = Newport('XCS:USR:MMN:03', name='samyag_z')
            #self.samyag_y = Newport('XCS:USR:MMN:06', name='samyag_y')
            #self.sam_x = Newport('XCS:USR:MMN:05', name='sam_x')
            #self.lens_z = IMS('XCS:USR:MMS:07',name = 'lens_z')

    def takeRun(self, nEvents, record=None, use_l3t=False):
        daq.configure(events=120, record=record, use_l3t=use_l3t)
        daq.begin(events=nEvents)
        daq.wait()
        daq.end_run()

    def ascan(self, motor, start, end, nsteps, nEvents, record=None, use_l3t=False):
        self.cleanup_RE()
        currPos = motor.wm()
        daq.configure(nEvents, record=record, controls=[motor], use_l3t=use_l3t)
        try:
            RE(scan([daq], motor, start, end, nsteps))
        except Exception:
            logger.debug('RE Exit', exc_info=True)
        finally:
            self.cleanup_RE()
        motor.mv(currPos)

    def pv_ascan(self, signal, start, end, nsteps, nEvents, record=None, use_l3t=False):
        self.cleanup_RE()
        currPos = signal.get()
        daq.configure(nEvents, record=record, controls=[signal], use_l3t=use_l3t)
        try:
            RE(scan([daq], signal, start, end, nsteps))
        except Exception:
            logger.debug('RE Exit', exc_info=True)
        finally:
            self.cleanup_RE()
        signal.put(currPos)

    def listscan(self, motor, posList, nEvents, record=None, use_l3t=False):
        self.cleanup_RE()
        currPos = motor.wm()
        daq.configure(nEvents, record=record, controls=[motor], use_l3t=use_l3t)
        try:
            RE(list_scan([daq], motor, posList))
        except Exception:
            logger.debug('RE Exit', exc_info=True)
        finally:
            self.cleanup_RE()
        motor.mv(currPos)

    def list3scan(self, m1, p1, m2, p2, m3, p3, nEvents, record=None, use_l3t=False):
        self.cleanup_RE()
        currPos1 = m1.wm()
        currPos2 = m2.wm()
        currPos3 = m3.wm()
        daq.configure(nEvents, record=record, controls=[m1,m2,m3], use_l3t=use_l3t)
        try:
            RE(list_scan([daq], m1,p1,m2,p2,m3,p3))
        except Exception:
            logger.debug('RE Exit', exc_info=True)
        finally:
            self.cleanup_RE()
        m1.mv(currPos1)
        m2.mv(currPos2)
        m3.mv(currPos3)

    def dscan(self, motor, start, end, nsteps, nEvents, record=None, use_l3t=False):
        self.cleanup_RE()
        daq.configure(nEvents, record=record, controls=[motor], use_l3t=use_l3t)
        currPos = motor.wm()
        try:
            RE(scan([daq], motor, currPos+start, currPos+end, nsteps))
        except Exception:
            logger.debug('RE Exit', exc_info=True)
        finally:
            self.cleanup_RE()
        motor.mv(currPos)

    def pv_dscan(self, signal, start, end, nsteps, nEvents, record=None, use_l3t=False):
        self.cleanup_RE()
        daq.configure(nEvents, record=record, controls=[signal], use_l3t=use_l3t)
        currPos = signal.get()
        try:
            RE(scan([daq], signal, currPos+start, currPos+end, nsteps))
        except Exception:
            logger.debug('RE Exit', exc_info=True)
        finally:
            self.cleanup_RE()
        signal.put(currPos)

    def a2scan(self, m1, a1, b1, m2, a2, b2, nsteps, nEvents, record=True, use_l3t=False):
        self.cleanup_RE()
        daq.configure(nEvents, record=record, controls=[m1, m2], use_l3t=use_l3t)
        try:
            RE(scan([daq], m1, a1, b1, m2, a2, b2, nsteps))
        except Exception:
            logger.debug('RE Exit', exc_info=True)
        finally:
            self.cleanup_RE()

    def a3scan(self, m1, a1, b1, m2, a2, b2, m3, a3, b3, nsteps, nEvents, record=True):
        self.cleanup_RE()
        daq.configure(nEvents, record=record, controls=[m1, m2, m3])
        try:
            RE(scan([daq], m1, a1, b1, m2, a2, b2, m3, a3, b3, nsteps))
        except Exception:
            logger.debug('RE Exit', exc_info=True)
        finally:
            self.cleanup_RE()

    def delay_scan(self, start, end, sweep_time, record=None, use_l3t=False,
                   duration=None):
        """Delay scan with the daq."""
        self.cleanup_RE()
        daq.configure(events=None, duration=None, record=record,
                      use_l3t=use_l3t, controls=[lxt_fast])
        try:
            RE(delay_scan(daq, lxt_fast, [start, end], sweep_time,
                          duration=duration))
        except Exception:
            logger.debug('RE Exit', exc_info=True)
        finally:
            self.cleanup_RE()

    def empty_delay_scan(self, start, end, sweep_time, record=None,
                         use_l3t=False, duration=None):
        """Delay scan without the daq."""
        self.cleanup_RE()
        #daq.configure(events=None, duration=None, record=record,
        #              use_l3t=use_l3t, controls=[lxt_fast])
        try:
            RE(delay_scan(None, lxt_fast, [start, end], sweep_time,
                          duration=duration))
        except Exception:
            logger.debug('RE Exit', exc_info=True)
        finally:
            self.cleanup_RE()

    def cleanup_RE(self):
        if not RE.state.is_idle:
            print('Cleaning up RunEngine')
            print('Stopping previous run')
            try:
                RE.stop()
            except Exception:
                pass
