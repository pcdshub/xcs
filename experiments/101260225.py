import numpy as np
from hutch_python.utils import safe_load
from xcs.db import xcs_gon as gon, ladm
from ophyd import EpicsMotor
import json
import sys
import os
import socket
import logging
from ophyd import EpicsSignal
from ophyd.device import Device
from ophyd.device import Component as Cpt

from pcdsdevices.device_types import Newport, IMS
from pcdsdevices.epics_motor import SmarAct, EpicsMotorInterface
from pcdsdevices.interface import BaseInterface
from pcdsdevices.sim import FastMotor
from xcs.db import RE, bpp, bps, seq, daq
#from xcs.db import daq
import matplotlib.pyplot as plt
from xcs.beamline import show_cc, show_delay

from bluesky import RunEngine
from bluesky.plans import scan
from bluesky.plans import list_scan
from pcdsdevices.device_types import Trigger

from hutch_python.utils import safe_load
import numpy as np
import logging
import time

THz_shutter = Newport('XCS:USR:MMN:12',name='THz_shutter')

class User():



    def THz_close(self):
        THz_shutter.mv(25)

    def THz_open(self):
        THz_shutter.mv(0)

#    def THz_800nm_shutter(self, exptime, offsettime,bothofftime):
#        i = 0
#      
#     
#        while 1:
#            # 800 open for offset time
#           
#            time.sleep(0.03)
#            shot_seq = []
#            shot_seq.append([94, 1, 0, 0])
#            seq.sequence.put_seq(shot_seq)
#            seq.start()
#            settime = exptime
#            time.sleep(settime)
#            seq.stop()
#            
#            # 800 nm open and both exposure
#           
#            settime = abs(exptime - offsettime)
#            time.sleep(0.03)
#            shot_seq = []
#            shot_seq.append([97, 1, 0, 0])
#            seq.sequence.put_seq(shot_seq)
#            seq.start()
#            time.sleep(settime)
#            seq.stop()
#            
#     
#            # ep close and only THz
#          
#            time.sleep(0.03)
#            shot_seq = []
#            shot_seq.append([95, 1, 0, 0])
#            seq.sequence.put_seq(shot_seq)
#            seq.start()
#            settime = exptime
#            time.sleep(settime)
#            seq.stop()
#
#                   # THz close and 800 nm only for offset time
#            self.lp_close() # both lp and ep close and lp open
#            time.sleep(0.03)
#            shot_seq = []
#            shot_seq.append([92, 1, 0, 0])
#            seq.sequence.put_seq(shot_seq)
#            seq.start()
#            settime = bothofftime
#            time.sleep(settime)
#            seq.stop()
#
#        return
#

with safe_load('Event Sequencers'):
    from pcdsdevices.sequencer import EventSequencer
    seq = EventSequencer('ECS:SYS0:4', name='seq')
    seq2 = EventSequencer('ECS:SYS0:11', name='seq2')




"""
class cdiff_SmarAct(BaseInterface, Device):
    tab_component_names = True

    sam_phi = Cpt(SmarAct, ':01:m4', kind='normal')
    sam_x = Cpt(SmarAct, ':01:m2', kind='normal')
    sam_z = Cpt(SmarAct, ':01:m3', kind='normal')
    sam_y = Cpt(SmarAct, ':01:m1', kind='normal')



class cdiff():#lib unit                                                                                                                                                                                            
    tab_component_names = True
    with safe_load('cdiff SmarAct'):
        lib = cdiff_SmarAct('XCS:MCS2', name='cdiff_smaract')

sam_phi = cdiff.lib.sam_phi
sam_y = cdiff.lib.sam_y
sam_x = cdiff.lib.sam_x
sam_z = cdiff.lib.sam_z
"""
