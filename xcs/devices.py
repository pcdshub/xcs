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
from pcdsdevices.analog_signals import Acromag

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
class Syringe_Pump():
    def __init__(self):
        self.signals = Acromag('XCS:USR', name='syringe_pump_channels')
        self.base = self.signals.ao1_0
        self.ttl = self.signals.ao1_1
    def on(self):
        ttl = self.ttl.get()
        self.base.put(5)
        if ttl == 5:
            self.ttl.put(0)
            print('Initialized and on')
        if ttl == 0:
            self.ttl.put(5)
            sleep(1)
            self.ttl.put(0)
            print("Syringe pump is on")
    def off(self):
        ttl = self.ttl.get()
        self.base.put(5)
        if ttl == 0:
            self.ttl.put(5)
            sleep(1)
            self.ttl.put(0)
            print("Syringe pump is off")
        if ttl == 5:
            self.ttl.put(0)

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









