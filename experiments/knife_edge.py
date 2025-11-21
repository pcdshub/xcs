import numpy as np
import json
import sys
import time
import os
import socket
import logging
from ophyd import EpicsSignal

from pcdsdevices.device_types import Newport, IMS
from xcs.db import RE, bpp, bps, seq, daq

from bluesky.plans import list_scan, scan
from bluesky.callbacks import LiveTable


#ljh_jet_x = EpicsSignal('XCS:LJH:JET:X')
#power = EpicsSignal('XCS:LPW:01:DATA_PRI')
#RE=RunEngine({})
#RE(bp.scan([power], ljh_jet_x, 15,17,20), LiveTable([ljh_jet_x])

#print("done")


class User():
    def __init__(self):
        self.ljh_jet_x = EpicsSignal('XCS:LJH:JET:X')
        self.power = EpicsSignal('XCS:LPW:01:DATA_PRI')

          


    def scan_with_delay(self, *args):

        try:
            daq.disconnect()
        except:
            print('DAQ might already be disconnected')
        daq.connect()
        daq.begin()

        RE(list_scan(dets, *args))

    def scan_daq(self, dets, ljh_jet_x, start, stop, num_steps):
        try:
            daq.disconnect()
        except:
            print('DAQ might already be disconnected')
        
        daq.connect()
        daq.begin()
        #RE(bp.list_scan([power], ljh_jet_x, [15.1,15.2,15.3]), LiveTable([ljh_jet_x])
        #RE(bp.scan([power], ljh_jet_x, 15,17,20), LiveTable([ljh_jet_x])
        yield from bp.scan([power], ljh_jet_x, 15,17,20)
        for i in range(20):
            yield from bluesky.plan_stubs.sleep(2)
        
        daq.end_run()

    RE(scan_daq([power], ljh_jet_x, 15, 17, 20)
    
