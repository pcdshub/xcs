from subprocess import check_output

import logging
import json
import sys
import time
import os

import numpy as np
from functools import reduce
from hutch_python.utils import safe_load
from ophyd.signal import EpicsSignalRO
from ophyd.signal import EpicsSignal
from bluesky.plans import scan
from bluesky.plans import list_scan
from bluesky.plan_stubs import monitor, unmonitor, open_run, close_run, sleep
from ophyd.device import Component as Cpt
from ophyd.device import FormattedComponent as FCpt
from ophyd import Device
from pcdsdevices.interface import BaseInterface
from pcdsdevices.areadetector import plugins
from pcdsdevices.gauge import BaseGauge
from xcs.db import daq, seq
from xcs.db import ipm4
from xcs.db import camviewer
from xcs.db import RE
from xcs.db import xcs_ccm as ccm
from xcs.delay_scan import delay_scan
from xcs.db import lxt_fast
from xcs.db import xcs_pulsepicker as pp
from xcs.db import xcs_attenuator as att
from xcs.db import lcls
from pcdsdevices.sequencer import EventSequencer
from pcdsdevices.device_types import Trigger as _Trigger
from threading import Event
from ophyd.utils.epics_pvs import set_and_wait
logger = logging.getLogger(__name__)


class LakeShoreChannel(BaseInterface, Device):
    """
    LakeShore temperature controller.

    Parameters
    ----------
    prefix : str
        ...
    channel : str
        Channel...

    """

    temp = FCpt(EpicsSignalRO, '{prefix}:GET_TEMP_{_channel}', kind='normal',
                doc='Channel Temperature [K/C/Sen]')

    unit = FCpt(EpicsSignal, '{prefix}:GET_UNITS_{_channel}', kind='normal',
                write_pv='{prefix}:PUT_UNITS_{_channel}',
                doc='Channel Units [K/C/Sen]')

    tab_component_names = False
    tab_whitelist = ['get_temp', 'get_units', 'set_units']

    def __init__(self, prefix, channel='A', **kwargs):
        self._channel = channel
        super().__init__(prefix, **kwargs)

    @property
    def get_temp(self, channel):
        """
        Temperature readback

        Parameters
        ----------
        channel : str
        """
        self.channel = channel
        return self.temp.get()

    @property
    def get_units(self, channel):
        """
        EGU readback

        Parameters
        ----------
        channel : str
        """
        self.channel = channel
        return self.unit.get()

    @property
    def set_units(self, channel, unit):
        """
        Set the desired temperature units

        Parameters
        ----------
        channel : str
            0 = K
            1 = C
            3 = Sen
        """
        self.channel = channel
        self.unit.put(unit)


class GasDetector(BaseInterface, Device):
    """
    A base class for a gas detector.

    Parameters
    ----------
    prefix : str
        Full gas detector base PV.

    name : str
       Name to refer to the gas detector
    """

    c0 = Cpt(EpicsSignal, ':241:ENRC')
    c0_egu = Cpt(EpicsSignalRO, ':241:ENRC.EGU', kind='normal',
               doc='Channel Units')
    c1 = Cpt(EpicsSignal, ':242:ENRC')
    c1_egu = Cpt(EpicsSignalRO, ':242:ENRC.EGU', kind='normal',
               doc='Channel Units')

    tab_component_names = False
    tab_whitelist = ['energy_24_avg', 'energy_241', 'energy_241_avg',
                     'units_241', 'energy_242', 'energy_242_avg',
                     'units_242']

    def _average_chan(self, chan, duration, md=None):
        """
        Average energy for one channel

        Parameters
        ----------
        channel : str
            c0 = GD -> :241
            c1 = GD -> :242
        num : int
            Number of seconds to run the monitor
        """
        values = []

        def data(*args, value, **kwargs):
            values.append(value)
            #print("data")
#check out beam stats.py in pcdsdevices
        cbid = chan.subscribe(data)
        #error handling (try/except block)
        time.sleep(duration/120.0)
        #print(values)
        avg = np.mean(values)
        chan.unsubscribe(cbid)
        return avg

    def _average_chans(self, duration, *chans):
        values = []
        def data(*args, value, **kwargs):
            values.append(value)
 
        for chan in chans:
            cbid = chan.subscribe(data)
            #error handling (try/except block)
            time.sleep(duration/120.0)
        avgs = [np.mean(values) for chan in chans]
        for chan in chans:
            chan.unsubscribe(cbid)
        return avgs

    def energy_24_avg(self, duration):
        """
        Average energies between gas detectors 241 and 242
        """
        return self._average_chans(duration, self.c0, self.c1)

    def energy_241(self):
        """
        Energy readback for Gas detector 241
        """

        return self.c0.get()

    def energy_241_avg(self, num):
        return self._average_chan(self.c0, num)

    def units_241(self):
        self.c0_egu.get()

    def energy_242(self):
        """
        Energy readback for Gas detector 242
        """

        return self.c1.get()

    def energy_242_avg(self, num):
        return self._average_chan(self.c1, num)

    def units_242(self):
        self.c1_egu.get()


class IPM4_Threshold:
    def __init__(self, threshold=0):
        self.set_threshold(threshold)

    def get_threshold(self):
       return self._threshold

    def set_threshold(self, Threshold):
        self._threshold = Threshold


class Trigger(_Trigger):
    tab_whitelist = ['enable', 'disable', 'get_eventcode', 'set_eventcode',
                     'label', 'get_delay', 'set_delay', 'get_polarity', 'set_polarity', 'set_width', 'set_width' ]
    tab_component_names = False

    def get_eventcode(self):
        return self.eventcode.get()

    def set_eventcode(self, num):
        return self.eventcode.put(num)

    def label(self):
        return self.label.get()

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


class actions:
    def __init__(self, value, name=''):
        self.name = name
        self.value = value


class User():
    def __init__(self):
        #switch to trigger instead of full evr
        self._sync_markers = {0.5:0, 1:1, 5:2, 10:3, 30:4, 60:5, 120:6, 360:7}
        self.trigger_mag = Trigger('XCS:R42:EVR:01:TRIG4', name='trigger_mag')
        self.trigger_pp = Trigger('XCS:USR:EVR:TRIG1', name='trigger_pp')
        self.nemptyshots = actions(0, name='nemptyshots')
        self.isfire = actions(False, name='isfire')
        self.emptyshotspacing = actions(0, name='emptyshotspacing')
        self.nshots = actions(0, name='nshots')
        self.shotspacing = actions(0, name='shotspacing')
        #with safe_load('Pirani and Cold Cathode Gauges'):
        #    self.mag_pirani = BaseGauge('XCS:USR:GPI:01', name='mag_pirani')
        #    self.mag_cc = BaseGauge('XCS:USR:GCC:01', name='mag_cc')
        self.sample_temp = LakeShoreChannel('XCS:USR:TCT:02', name='A')
        self.mag_temp = LakeShoreChannel('XCS:USR:TCT:02', name='B')
        self.ttl_high = 2.0
        self.ttl_low = 0.8
        self._ready_sig = EpicsSignal('XCS:USR:ai1:0', name='User Analog Input channel 0', kind = 'omitted')
        self._ipm4_threshold = IPM4_Threshold(0) #default threshold is 0
        self.ipm4_pv = EpicsSignal('XCS:SB1:BMMON:SUM', name='ipm4_sum')
        self.ipm4_mag_retry = 10
        self._gdet_threshold_pv = EpicsSignal('XCS:VARS:J78:GDET_THRES', kind = 'normal')
        self.gdet_avg_count = 30
        self.gdet_mag_retry = 10
        self.gdet = GasDetector('GDET:FEE1', name='gas detector')
        #self._bykik_pv = Cpt(EpicsSignal('IOC:IN20:EV01:BYKIK_ABTACT', kind = 'normal', string=True, doc='BYKIK: Abort Active')
        self._req_burst_rate = 'Full'
        self._test_burst_rate = EpicsSignal('PATT:SYS0:1:TESTBURSTRATE', name='test_burst_rate', kind='normal')
        self._mps_burst_rate = EpicsSignal('PATT:SYS0:1:MPSBURSTRATE', name='mps_burst_rate')
        # number of seconds to pause between empty and magnet
        self.pause_time = 2.
        self._min_empty_delay = 4 
        self._beam_owner = EpicsSignal('ECS:SYS0:0:BEAM_OWNER_ID', name='beam_owner', kind = 'normal')
        self._att = att
        self.hutch = 'xcs'
        self._hutch_id = EpicsSignal('ECS:SYS0:4:HUTCH_ID', name='hutch_id', kind = 'normal')
        self.aliases = ['BEAM']
        self.gainmodes = ''

#use lcls.(tab) to find bykik controls

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

    @property
    def ready_sig(self):
        self._ready_sig.get()

#    def prepare_burst(self, nShots=None, nWaitShots=None):
#        sync_mark = int(self._sync_markers[120])
#        seq.sync_marker.put(sync_mark)
#        seq.play_mode.put(0)
#        ff_seq = [[84,0,0,0]]
#        ff_seq = ff_seq.append([86, 2, 0, 0])
#        if nShots is not None:
#            if isinstance(nShots, int):
#                ff_seq.append([84, nShots-2, 0, 0])
#        else:
#            ff_seq.append([84, int(nShots*120)-2, 0, 0])
#        if isinstance(nWaitShots, int):
#            ff_seq.append([86, nWaitShots-2, 0, 0])
#        seq.sequence.put_seq(ff_seq)
        
    def _prepare_burst(self, Nshots, Nbursts=1, freq=120, delay=None, burstMode=False):
        if Nshots == 1:
            pp.flipflop()
        elif Nshots > 1:
            pp.burst()
        beamrate = lcls.beam_event_rate.get()
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
    def _prepNonMagShots(self, nshots):
        #copy code from old pulsepicker.py file in (blinst) and change where needed or xpp experiment
        self._prepare_burst(nshots, burstMode=True)

    def _prepSpacedNonMagShots(self, nshots_per_burst, spacing):
        nshots = 1
        burstDelay = spacing - 2
        self.prepare_burst(nshots, Nbursts=nshots_per_burst, delay=burstDelay, burstMode=True)

    def _takeNonMagShots(self):
        seq.start()

    def _prepMagShot(self, isfire, delay=1):
        playcount = int(seq.play_count.get())
        
        pp.flipflop()
        seq.play_mode.put(0)
        ff_seq = [ [84,delay,0,3],
                       [86,0,0,0] ]
        if isfire:
            ff_seq.append([self.trigger_mag.get_eventcode(), 2, 0, 0])
            ff_seq.append([85, 0, 0, 0])
        else:
            ff_seq.append([85, 2, 0, 0])
        seq.sequence.put_seq(ff_seq)
        playcount += 1
        seq.play_count.put(playcount)
    

    def _takeMagShot(self):
        seq.start()

    def takeEmptyShots(self, nshots, shotspacing, use_daq=False, record=None):
        self.nshots.value = nshots
        self.shotspacing.value = shotspacing
        calibcontrols=[
            (self.nshots),
            (self.shotspacing)
           ]
        if shotspacing > 0:
            self._prepSpacedNonMagShots(self.nshots.value, self.shotspacing.value)
        else:
            self._prepNonMagShots(self.nshots.value)
        #configure daq if being used
        if use_daq:
            daq.record = record
            daq.configure(events=0, controls=calibcontrols)
        try:
            if use_daq:
                daq.begin(event=nshots,controls=calibcontrols)
            seq.start()
            seq.pause()
            if use_daq:
                daq.wait()
        except KeyboardInterrupt:
            seq.stop()
        finally:
            if use_daq:
                daq.record = None
                daq.disconnect()

    def takeMagnetShot(self, nemptyshots, emptyshotspacing=0, isfire=False, record=None):
        self.isfire.value = isfire
        self.nemptyshots.value = nemptyshots
        self.emptyshotspacing.value=emptyshotspacing
        calibcontrols=[
            (self.isfire),
            (self.trigger_mag),
            (self.trigger_mag),
            (self.trigger_mag),
            (self.nemptyshots),
            (self.emptyshotspacing)
           ]
        # check the machine burst rate and set to Full rate if not
        self.check_burst_rate()
        # disable BYKIK before taking shots
        lcls.bykik_disable()
          # check if emptyshotspacing is valid
        if 0 < self.emptyshotspacing.value < self._min_empty_delay:
            raise ValueError("When using spacing between empty shots it must be >= %d" %self._min_empty_delay)
        spacer = "*********************************"
        print("\n%s\n* Preparing to take magnet shot *\n%s\n" %(spacer, spacer))
        if emptyshotspacing > 0:
            mag_status  = "Taking %d shots, with a spacing between each of %d beam pulses, before firing the magnet\n" %(self.nemptyshots.value, self.emptyshotspacing.value)
        else:
            mag_status  = "Taking %d shots before firing the magnet\n" %self.nemptyshots.value
        mag_status += "Magnet pulse eventcode: %d\n" %self.trigger_mag.get_eventcode()
        mag_status += "Magnet pulse trigger delay: %f\n" %self.trigger_mag.get_delay()
        mag_status += "Magnet pulse trigger width: %f\n" %self.trigger_mag.get_width()
        mag_status += "Magnet to be fired: %s\n" %self.isfire.value
        print(mag_status)
        try:
            daq.record = record
            daq.configure(events=0, controls=calibcontrols)
            # Pre empty shots
            if self.nemptyshots.value > 0:
                print("\nPreparing sequencer for pre-firing, non-magnet shots")
                if self.emptyshotspacing.value > 0:
                    self._prepSpacedNonMagShots(self.nemptyshots.value, self.emptyshotspacing.value)
                else:
                    self._prepNonMagShots(self.nemptyshots.value)
                daq.begin(events=self.nemptyshots.value,controls=calibcontrols)
                print("\nTaking %d pre-firing, non-magnet shots\n" %self.nemptyshots.value)
                # pause after changing pulse picker mode
                time.sleep(self.pause_time)
                self._takeNonMagShots()
                seq.pause()
                daq.wait()
            else:
                print("\nSkipping prefiring, non-magnet shots\n")
            # pause after empty shots
            time.sleep(self.pause_time)
            # Fire the magnet sequence based on isfire flag
            if isfire:
                print("Start magnet firing sequence\n")
            else:
                print("Start magnet test 'firing' sequence\n")
            print("\nPreparing sequencer for magnet shot")
            if self.emptyshotspacing.value > 0:
                self._prepMagShot(self.isfire.value, self.emptyshotspacing.value)
            else:
                self._prepMagShot(self.isfire.value)
            # pause after changing pulse picker mode
            time.sleep(self.pause_time)
            #checking ipm4??
            num_tries = 0
            ipm4_good = False
            while num_tries < self.ipm4_mag_retry:
                if self.ipm4_pv < self._ipm4_threshold:
                    print("\nNot firing magnet due to low beam current (ipm4): %.3f \n" %(self.ipm4_pv.get()))
                    backoff_time = 2 ** num_tries
                    print("Sleeping for %d seconds...\n" %backoff_time)
                    time.sleep(backoff_time)
                    num_tries += 1
                else:
                    #ipm4 is good - fire!
                    ipm4_good = True
                    print("\nIPM4 looks good (ipm4): %.3f\n" %self.ipm4_pv.get())
                    break
            if not ipm4_good:
                print("Max number of ipm4 checks (%d) exceeded! - Abort shot attempt.\n" %self.ipm4_mag_retry)
                return False
            # take the magnet shot
            daq.begin(events=1,controls=calibcontrols)
            print("\nTaking magnet shot\n")
            self._takeMagShot()
            seq.pause()
            daq.wait()
            #pause after magnet shots
            time.sleep(self.pause_time)
            #post empty shots
            if nemptyshots > 0:
                print("\nPreparing sequencer for post-firing, non-magnet shots")
                if self.emptyshotspacing.value > 0:
                    self._prepSpacedNonMagShots(self.nemptyshots.value, self.emptyshotspacing.value)
                else:
                    self._prepNonMagShots(self.nemptyshots.value)
                daq.begin(events=self.nemptyshots.value,controls=calibcontrols)
                print("\nTaking %d post-firing, non-magnet shots\n" %self.nemptyshots.value)
                # pause after changing pulse picker mode
                time.sleep(self.pause_time)
                self._takeNonMagShots()
                seq.pause()
                daq.wait()
            else:
                print("\nSkipping post-firing, non-magnet shots\n")
            return True
        except KeyboardInterrupt:
            seq.stop()
            daq.stop()
            return False
        finally:
            daq.record = None
            daq.disconnect()
            lcls.bykik_enable()
    def takeMagnetShotMulti(self, nemptyshots, emptyshotspacing=0, isfire=False, record=None, ignore_ready=False):
        """
        Takes magnet shots in a continous fashion waiting for a ready signal from the magnet controller
        """
        self.nemptyshots.value = nemptyshots
        self.emptyshotspacing.value = emptyshotspacing
        self.isfire.value = isfire
        latch = False
        nmagshots = 0
        shotgood = True
        spacer = '##############################'
        try:
            while shotgood:
                if not latch and (self.ready_sig > self.ttl_high or ignore_ready):
                    if self.ipm4_pv < self._ipm4_threshold:
                        print("\nNot firing magnet due to low beam current (ipm4): %.3f \n" %(self.ipm4_pv.get()))
                        backoff_time = 1
                        print("Sleeping for %d second...\n" %backoff_time)
                        time.sleep(backoff_time)
                        continue
                    latch = True
                    print("\n%s\nStarting shot %d\n%s\n" %(spacer,nmagshots,spacer))
                    start_time = time.time()
                    shotgood = self.takeMagnetShot(self.nemptyshots.value, self.emptyshotspacing.value, self.isfire.value, record)
                    stop_time = time.time()
                    print("\n%s\nCompleted shot %d in %.2f s\n%s\n" %(spacer,nmagshots,(stop_time-start_time),spacer))
                    nmagshots += 1
                if latch and (self.ready_sig < self.ttl_low or ignore_ready):
                    latch = False
                time.sleep(0.25)
        except KeyboardInterrupt:
            print('\nExiting...\n')
        finally:
            print('Took %d total magnet shots\n' %nmagshots)  

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

