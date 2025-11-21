from subprocess import check_output

import logging
import json
import sys
import time
import os

import numpy as np
import elog
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
from xcs.db import bec
from xcs.db import xcs_ccm as ccm
from xcs.delay_scan import delay_scan
from xcs.db import lxt_fast, lxt_fast_enc
from pcdsdevices.device_types import Newport, IMS
from pcdsdevices.evr import Trigger

#from macros import *
import time

logger = logging.getLogger(__name__)
 
 

class User():
    def __init__(self):
        with safe_load ('LED'):
            self.led = Trigger('XCS:R42:EVR:01:TRIG9', name='led_delay')


    def delay_scan(self, start, end, sweep_time, record=True, use_l3t=False,
                   duration=None):
        """Delay scan with the daq."""
        self.cleanup_RE()
        bec.disable_plots()
        controls = [lxt_fast]
        try:
            RE(delay_scan(daq, lxt_fast, [start, end], sweep_time,
                          duration=duration, record=record, use_l3t=use_l3t,
                          controls=controls))
        except Exception:
            logger.debug('RE Exit', exc_info=True)
        finally:
            self.cleanup_RE()
            bec.enable_plots()

    def empty_delay_scan(self, start, end, sweep_time, record=True,
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
    
    def lxt_fast_set_absolute_zero(self):
        currentpos = lxt_fast()
        currentenc = lxt_fast_enc.get()
        #elog.post('Set current stage position {}, encoder value {} to 0'.format(currentpos,currentenc.pos))
        print('Set current stage position {}, encoder value {} to 0'.format(currentpos,currentenc.pos))
        lxt_fast.set_current_position(0)
        lxt_fast_enc.set_zero()
        return

    def cleanup_RE(self):
        if not RE.state.is_idle:
            print('Cleaning up RunEngine')
            print('Stopping previous run')
            try:
                RE.stop()
            except Exception:
                pass






