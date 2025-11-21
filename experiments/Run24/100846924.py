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
        with safe_load ('experiment sample motors'):
            self.tilt_x = IMS('XCS:USR:MMS:35', name='tilt_x')
            self.tilt_z = IMS('XCS:USR:MMS:45', name='tilt_z')
            self.sam_z = IMS('XCS:USR:MMS:41', name='sam_z')
            self.sam_x = IMS('XCS:USR:MMS:42', name='sam_x')
            self.sam_y = IMS('XCS:USR:MMS:43', name='sam_y')
            self.sam_theta = IMS('XCS:USR:MMS:44', name='sam_theta')

    def lxt_fast_set_absolute_zero(self):
        currentpos = lxt_fast()
        currentenc = lxt_fast_enc.get()
        #elog.post('Set current stage position {}, encoder value {} to 0'.format(currentpos,currentenc.pos))
        print('Set current stage position {}, encoder value {} to 0'.format(currentpos,currentenc.pos))
        lxt_fast.set_current_position(0)
        lxt_fast_enc.set_zero()
        return

    def takeRun(self, nEvents=None, duration=None, record=True, use_l3t=False):
        daq.configure(events=120, record=record, use_l3t=use_l3t)
        daq.begin(events=nEvents, duration=duration)
        daq.wait()
        daq.end_run()
