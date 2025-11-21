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
from bluesky.plan_stubs import monitor, unmonitor, open_run, close_run, sleep
from ophyd import Component as Cpt
from ophyd import Device
from pcdsdevices.interface import BaseInterface
from pcdsdevices.areadetector import plugins
from xcs.db import daq, seq
from xcs.db import camviewer
from xcs.db import RE
from pcdsdevices.device_types import Newport, IMS

from xcs.db import xcs_pulsepicker as pp
from xcs.db import xcs_attenuator as att
from xcs.db import lcls
from pcdsdevices.sequencer import EventSequencer
from pcdsdevices.device_types import Trigger as _Trigger
from pcdsdevices.signal import AvgSignal
from threading import Event
from ophyd.utils.epics_pvs import set_and_wait



#from macros import *
import time

logger = logging.getLogger(__name__)

class Trigger(_Trigger):
    tab_whitelist = ['enable', 'disable', 'get_eventcode', 'set_eventcode',
                     'label', 'get_delay', 'set_delay', 'get_polarity', 'set_polarity', 'set_width', 'set_width' ]
    tab_component_names = False

    def get_eventcode(self):
        return self.eventcode.get()

    def set_eventcode(self, num):
        return self.eventcode.put(num)

    def get_delay(self):
        return self.ns_delay.get()

    def set_delay(self, num):
        return self.ns_delay.put(num)

    def get_polarity(self):
        return self.polarity.get()

    def set_polarity(self, num):
        """
        Function for setting polarity        

        Parameters
        ----------
        num = int
            0 = normal
            1 = inverted 
        """
        return self.polarity.put(num)

    def get_width(self):
        return self.width.get()

    def set_width(self, num):
        """
        Function for setting width

        Parameters
        ----------
        num = int [ns]
        """
        return self.width.put(num)


class ConfigVal:
    def __init__(self, value):
        self.position = value



class User():
    def __init__(self):
        with safe_load('x489_motor'):
            self.detx = Newport('XCS:USR:MMN:16', name='detx')
            self.dety = IMS('XCS:USR:MMS:40', name='dety')
            self.detz = Newport('XCS:USR:MMN:08', name='detz')

        self._sync_markers = {0.5:0, 1:1, 5:2, 10:3, 30:4, 60:5, 120:6, 360:7}
        self.trigger_mag = Trigger('XCS:R42:EVR:01:TRIG4', name='trigger_mag')
        self.trigger_pp = Trigger('XCS:USR:EVR:TRIG1', name='trigger_pp')
        self._req_burst_rate = 'Full'
        self._test_burst_rate = EpicsSignal('PATT:SYS0:1:TESTBURSTRATE', name='test_burst_rate', kind='normal')
        self._mps_burst_rate = EpicsSignal('PATT:SYS0:1:MPSBURSTRATE', name='mps_burst_rate')
        self.pause_time = 2.
        self._min_empty_delay = 4 
        self._beam_owner = EpicsSignal('ECS:SYS0:0:BEAM_OWNER_ID', name='beam_owner', kind = 'normal')
        self._att = att
        self.hutch = 'xcs'
        self._hutch_id = EpicsSignal('ECS:SYS0:4:HUTCH_ID', name='hutch_id', kind = 'normal')
        self.aliases = ['BEAM']
        self.gainmodes = ''

    @property
    def machine_burst_rate(self):
        if self._beam_owner.get() == self._hutch_id.get():
            self._mps_burst_rate.get()
        else:
            self._test_burst_rate.get()

    @machine_burst_rate.setter
    def machine_burst_rate(self, rate):
        if self._beam_owner.get() == self._hutch_id.get():
            self._mps_burst_rate.put(rate)
        else:
            self._test_burst_rate.put(rate)

    def check_burst_rate(self):
        if self.machine_burst_rate != self._req_burst_rate:
            print('Machine burst frequency not set to %s! - fixing...' %self._req_burst_rate)
            if self._beam_owner.get() == self._hutch_id.get():
                set_and_wait(self._mps_burst_rate, self._req_burst_rate)  #ophyd set and wait() - ophyd.utils.epics_pvs.set_and_wait
            else:
                set_and_wait(self._test_burst_rate, self._req_burst_rate)
            print('done.')


    def seq_wait(self, timeout=0, sleeptime=1.0):
        print(f'timeout = {timeout}, sleep = {sleeptime}')
        sleep(sleeptime)
        start = time.time()
        print(f'start time: {start}')
        while seq.play_status.get() != 0:
            if timeout > 0 and (time.time() - start >= timeout):
                raise ValueError('Timed out')
        
    def _prepare_burst(self, Nshots, Nbursts=1, freq=120, delay=None, burstMode=False):
        if Nshots == 1:
            pp.flipflop()
        elif Nshots > 1:
            pp.burst()
        if Nbursts == 1:
            seq.play_mode.put(0)
        elif Nbursts > 1:
            seq.play_mode.put(1)
            seq.rep_count.put(Nbursts)
        elif Nbursts < 0:
            seq.play_mode.put(2)
        if burstMode:
            burst = Nshots + 2
        else:
            burst = 0
        if not freq == 120:
            raise(NotImplementedError('Not implemented yet!'))
        if Nshots == 1:
            if delay is None:
                delay = 3
            elif delay < 2:
                raise ValueError('Delay between flip flops of less than two is not allowed')
            ff_seq = [[84,delay,0,burst],
                       [86,0,0,burst],
                       [85,2,0,burst]]
        elif Nshots > 1:
            if delay is None:
                delay = 1
            elif delay < 1:
                raise ValueError('Delay between bursts of less than one is not allowed')
            ff_seq = [ [84,delay,0,burst],
                       [86,0,0,burst],
                       [86,1,0,burst] ]
            for shotNo in range(Nshots):
                ff_seq.append([85, 1, 0, burst])
                if shotNo==Nshots-2:
                    ff_seq.append([84, 0, 0, burst])

        seq.sequence.put_seq(ff_seq)

    def _prepShots(self, nshots):
        #copy code from old pulsepicker.py file in (blinst) and change where needed or xpp experiment
        self._prepare_burst(nshots, burstMode=True)

    def _prepSpacedShots(self, nshots_per_burst, spacing):
        nshots = 1
        burstDelay = spacing - 2
        self.prepare_burst(nshots, Nbursts=nshots_per_burst, delay=burstDelay, burstMode=True)

    def takePulepickerShots(self, nshots, shotspacing, use_daq=False, record=None):
        calibcontrols={
            'nshots': ConfigVal(nshots),
            'shotspacing': ConfigVal(shotspacing)
        }

        if shotspacing > 0:
            self._prepSpacedShots(nshots, shotspacing)
        else:
            self._prepShots(nshots)
        #configure daq if being used
        if use_daq:
            daq.record = record
            daq.configure(events=0, controls=calibcontrols)
        try:
            if use_daq:
                daq.begin(events=nshots,controls=calibcontrols)
            seq.start()
            self.seq_wait()
            if use_daq:
                daq.wait()
        except KeyboardInterrupt:
            seq.stop()
        finally:
            if use_daq:
                daq.record = None
                daq.disconnect()

    def takeRun(self, nEvents, record=None, use_l3t=False):
        daq.configure(events=120, record=record, use_l3t=use_l3t)
        daq.begin(events=nEvents)
        daq.wait()
        daq.end_run()


    def cleanup_RE(self):
        if not RE.state.is_idle:
            print('Cleaning up RunEngine')
            print('Stopping previous run')
            try:
                RE.stop()
            except Exception:
                pass



