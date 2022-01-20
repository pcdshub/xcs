# Modified by tcouto 3/4/2014 for trigger mode "LE=Level Control"
from epics import PV 
import pyca
#from psp import PV
from time import sleep
from ophyd import (Device, EpicsSignal, EpicsSignalRO, Component as Cpt,
                   FormattedComponent as FCpt)
from ophyd.signal import AttributeSignal

import pcdsdevices.device_types
from pcdsdevices.inout import InOutPositioner
from subprocess import check_output
import time

class LaserShutter(InOutPositioner):
    """Controls shutter controlled by Analog Output"""
    # EpicsSignals
    voltage = Cpt(EpicsSignal, '')
    state = FCpt(AttributeSignal, 'voltage_check')
    # Constants
    out_voltage = 4.5
    in_voltage = 0.0
    barrier_voltage = 1.4

    @property
    def voltage_check(self):
        """Return the position we believe shutter based on the channel"""
        if self.voltage.get() >= self.barrier_voltage:
            return 'OUT'
        else:
            return 'IN'

    def _do_move(self, state):
        """Override to just put to the channel"""
        if state.name == 'IN':
            self.voltage.put(self.in_voltage)
        elif state.name == 'OUT':
            self.voltage.put(self.out_voltage)
        else:
            raise ValueError("%s is in an invalid state", state)


#TTL I/O Operational Trigger
class SyringePump:
    def __init__(self,name,base,ttl,vlow=0,vhigh=5):
        self.name=name
        self.base=PV(base)
        self.ttl=PV(ttl)
        self.vlow=vlow
        self.vhigh=vhigh
        self.delta=0.5
        self._is_initialized=False
    def _initialize(self):
        if not self._is_initialized:
            self.base.put(self.vhigh)
            self.ttl.put(self.vlow)
        self._is_initialized=True	
    def _uninitialize(self):
        if self._is_initialized:
            self.base.put(self.vlow)
            self.ttl.put(self.vlow)
        self._is_initialized=False	
    def on(self):
        if not self._is_initialized:
            self._initialize()
        self.ttl.put(self.vhigh)
        sleep(1)
        self.ttl.put(self.vlow)
        sleep(1)
        self.ttl.put(self.vhigh)
    def off(self):
        if not self._is_initialized:
            self._initialize()
        self.ttl.put(self.vhigh)
        sleep(1)
        self.ttl.put(self.vlow)
    def status_string(self):
        status_string='Syringepump is in unknown state'
        if not self._is_initialized:
            status_string='Syringepump is not initialized'
        else:
            if abs(self.ttl.get()-self.vhigh)<self.delta:
                status_string='Syringepump is ON'
            elif abs(self.ttl.get()-self.vlow)<self.delta:
                status_string='Syringepump is OFF'
        return status_string
    def status(self):
        print(self.status_string())
    def __repr__(self):
        return self.status_string()
    def test(self):
        if not self._is_initialized:
            self._initialize()
        self.on()
        sleep(5)
        self.off()

#RS-232 operation
from telnetlib import Telnet
import re

class SyringePumpSerial():
    status_dict = {
        'I': 'Infusing',
        'W': 'Withdrawing',
        'S': 'Program Stopped',
        'P': 'Program Paused',
        'T': 'Timed Pause Phase',
        'U': 'Waiting for Trigger',
        'X': 'Purging',
    }

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def cmd(self, command):
       print(self.send_command(command))

    def send_command(self, command):
        with Telnet(self.host,self.port) as t:
            t.write(command.encode()+b'\r')
            msg = t.read_some().decode('ascii')
            regex = re.search('\x0200(\D)(.*)\x03', msg)
            status = self.status_dict[regex.group(1)]
            return f"""\
Command:\t{command}
Response:\t{regex.group(2)}
Status:\t\t{status}
"""

    def run(self):
        self.cmd('RUN')

    def stop(self):
        self.cmd('STP')

    def __call__(self, command):
        self.cmd(command)

    def __repr__(self):
        return self.send_command('')

    def timed(self, seconds):
        self.run()
        sleep(seconds)
        self.stop()









