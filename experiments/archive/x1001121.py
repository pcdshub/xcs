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
#from xcs.db import bec
from xcs.db import xcs_ccm as ccm
from xcs.delay_scan import delay_scan
from xcs.db import lxt_fast, lxt_fast_enc
from pcdsdevices.device_types import Newport, IMS
from pcdsdevices.evr import Trigger
from epics import caget 

#from macros import *
import time

logger = logging.getLogger(__name__)

#from xpp.db import daq, seq, elog
#from ophyd.status import wait as status_wait
from pcdsdevices.evr import Trigger
#from xpp.db import cp
#from xpp.db import lp
#from xpp.db import xpp_pulsepicker as pp
#from xpp.db import xpp_ccm as ccm
#from pcdsdevices.device_types import Newport, IMS
# WAIT A WHILE FOR THE DAQ TO START
#import pcdsdaq.daq
#pcdsdaq.daq.BEGIN_TIMEOUT = 5



#######################
class User:
    """Generic User Object"""
    with safe_load('Dummy'):
        print('Import dummy')

    def __init__(self):

#        with safe_load ('VH_motors'):
#            self.vh_y = IMS('XCS:USR:MMS:02', name='vh_y')
#            self.vh_x = IMS('XCS:USR:MMS:03', name='vh_x')

#        with safe_load('Von Hamos Beckhoff'):
#            from pcdsdevices.epics_motor import BeckhoffAxis
#            class VonHamos_Spec(Device):
#                cr1_move = Cpt(BeckhoffAxis, ':01', name='cr1_move')
#                cr2_move = Cpt(BeckhoffAxis, ':02', name='cr2_move')
#                cr3_move = Cpt(BeckhoffAxis, ':03', name='cr3_move')
#                cr4_move = Cpt(BeckhoffAxis, ':04', name='cr4_move')
#                cr1_rot = Cpt(BeckhoffAxis, ':01', name='cr1_rot')
#                cr2_rot = Cpt(BeckhoffAxis, ':02', name='cr2_rot')
#                cr3_rot = Cpt(BeckhoffAxis, ':03', name='cr3_rot')
#                cr4_rot = Cpt(BeckhoffAxis, ':04', name='cr4_rot')
#            self.vhs = VonHamos_Spec('MFX:VHS:MMB', name='vhs')

        with safe_load ('LED'):
            #self.led = Trigger('XCS:R42:EVR:01:TRIG9', name='led_delay')
            self.led = Trigger('XCS:R44:EVR:44:TRIG6', name='led_delay')
            self.led_uS = MicroToNano()

#        with safe_load('Laser Phase Motor'):
#            from ophyd.epics_motor import EpicsMotor
#            self.las_phase = EpicsMotor('LAS:FS4:MMS:PH', name='las_phase')

    def set_current_position(self, motor, value):
        motor.set_use_switch.put(1)
        motor.set_use_switch.wait_for_connection()
        motor.user_setpoint.put(value, force=True)
        motor.user_setpoint.wait_for_connection()
        motor.set_use_switch.put(0)
    def led_scan(self, start, end, nsteps, duration):
        """
        Function to scan led delays and dwell at each delay. Goes back to original delay after scanning.

        Parameters
        ---------
        start : float
            Start delay in microseconds.
        end : float
            End delay in microseconds.
        nsteps : integer
            number of steps for delay.
        duration : float
            Dwell time at each delay. In seconds.
        """
        old_led = self.led.ns_delay.get()
        print('Scanning LED delays...')
        steps = np.linspace(start * 1000.0, end * 1000.0, nsteps)
        for step in steps:
            self.led.ns_delay.put(step)
            time.sleep(duration)
        self.led.ns_delay.put(old_led)
        print('Scan complete setting delay back to old value: ' +str(old_led))

    def lxt_fast_set_absolute_zero(self):
        currentpos = lxt_fast()
        currentenc = lxt_fast_enc.get()
        #elog.post('Set current stage position {}, encoder value {} to 0'.format(currentpos,currentenc.pos))
        print('Set current stage position {}, encoder value {} to 0'.format(currentpos,currentenc.pos))
        lxt_fast.set_current_position(0)
        lxt_fast_enc.set_zero()
        return

    def takeRun(self, nEvents, record=True, use_l3t=False):
        daq.configure(events=120, record=record, use_l3t=use_l3t)
        daq.begin(events=nEvents)
        daq.wait()
        daq.end_run()

    def pvascan(self, motor, start, end, nsteps, nEvents, record=None):
        currPos = motor.get()
        daq.configure(nEvents, record=record, controls=[motor])
        RE(scan([daq], motor, start, end, nsteps))
        motor.put(currPos)

    def pvdscan(self, motor, start, end, nsteps, nEvents, record=None):
        daq.configure(nEvents, record=record, controls=[motor])
        currPos = motor.get()
        RE(scan([daq], motor, currPos + start, currPos + end, nsteps))
        motor.put(currPos)

    #def ascan(self, motor, start, end, nsteps, nEvents, record=True, use_l3t=False):
    #    self.cleanup_RE()
    #    currPos = motor.wm()
    #    daq.configure(nEvents, record=record, controls=[motor], use_l3t=use_l3t)
    #    try:
    #        RE(scan([daq], motor, start, end, nsteps))
    #    except Exception:
    #        logger.debug('RE Exit', exc_info=True)
    #    finally:
    #        self.cleanup_RE()
    #    motor.mv(currPos)

    def listscan(self, motor, posList, nEvents, record=True, use_l3t=False):
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

    #def dscan(self, motor, start, end, nsteps, nEvents, record=True, use_l3t=False):
    #    self.cleanup_RE()
    #    daq.configure(nEvents, record=record, controls=[motor], use_l3t=use_l3t)
    #    currPos = motor.wm()
    #    try:
    #        RE(scan([daq], motor, currPos+start, currPos+end, nsteps))
    #    except Exception:
    #        logger.debug('RE Exit', exc_info=True)
    #    finally:
    #        self.cleanup_RE()
    #    motor.mv(currPos)

    #def a2scan(self, m1, a1, b1, m2, a2, b2, nsteps, nEvents, record=True, use_l3t=False):
    #    self.cleanup_RE()
    #    daq.configure(nEvents, record=record, controls=[m1, m2], use_l3t=use_l3t)
    #    try:
    #        RE(scan([daq], m1, a1, b1, m2, a2, b2, nsteps))
    #    except Exception:
    #        logger.debug('RE Exit', exc_info=True)
    #    finally:
    #        self.cleanup_RE()

    #def a3scan(self, m1, a1, b1, m2, a2, b2, m3, a3, b3, nsteps, nEvents, record=True):
    #    self.cleanup_RE()
    #    daq.configure(nEvents, record=record, controls=[m1, m2, m3])
    #    try:
    #        RE(scan([daq], m1, a1, b1, m2, a2, b2, m3, a3, b3, nsteps))
    #    except Exception:
    #        logger.debug('RE Exit', exc_info=True)
    #    finally:
    #        self.cleanup_RE()

    #def delay_scan(self, start, end, sweep_time, record=True, use_l3t=False,
    #               duration=None):
    #    """Delay scan with the daq."""
    #    self.cleanup_RE()
    #    bec.disable_plots()
    #    controls = [lxt_fast]
    #    try:
    #        RE(delay_scan(daq, lxt_fast, [start, end], sweep_time,
    #                      duration=duration, record=record, use_l3t=use_l3t,
    #                      controls=controls))
    #    except Exception:
    #        logger.debug('RE Exit', exc_info=True)
    #    finally:
    #        self.cleanup_RE()
    #        bec.enable_plots()

    #def empty_delay_scan(self, start, end, sweep_time, record=True,
    #                     use_l3t=False, duration=None):
    #    """Delay scan without the daq."""
    #    self.cleanup_RE()
    #    #daq.configure(events=None, duration=None, record=record,
    #    #              use_l3t=use_l3t, controls=[lxt_fast])
    #    try:
    #        RE(delay_scan(None, lxt_fast, [start, end], sweep_time,
    #                      duration=duration))
    #    except Exception:
    #        logger.debug('RE Exit', exc_info=True)
    #    finally:
    #        self.cleanup_RE()

    def cleanup_RE(self):
        if not RE.state.is_idle:
            print('Cleaning up RunEngine')
            print('Stopping previous run')
            try:
                RE.stop()
            except Exception:
                pass

    def scanExamples(self):
        print("""
        Absolute Scan
          re.daq_ascan([], sim.fast_motor1, -1, 1, 21, events = 10, record = False)

        Absolute 2D Scan
          re.daq_a2scan([], sim.fast_motor1, -1, 1 , sim.fast_motor2, -1, 1, nsteps = 5, events = 10, record = False)

        Absolute 3D Scan
          re.daq_a3scan([], sim.fast_motor1, -1, 1 , sim.fast_motor2, -1, 1, sim.fast_motor3, -1, 1, nsteps = 5, events = 10, record = False)

        Delta Scan
          re.daq_dscan([], sim.fast_motor1, -1, 1, 21, events = 10, record = False)

        Delay Scan
          re.daq_delay_scan([], lxt_fast, [-1e-12, 1e-12], sweep_time = 5,  duration = 20, record = False)

        Empty Delay Scan (no Daq)
          re.delay_scan([], lxt_fast, [-1e-12,1e-12], sweep_time = 5,  duration = 20)
        """)


    ##########################
    # CCM Scanning Functions #
    ##########################
    def perform_run(self, events, record=True, comment='', post=True,
                    **kwargs):
        """
        Perform a single run of the experiment

        Parameters
        ----------
        events: int
            Number of events to include in run

        record: bool, optional
            Whether to record the run

        comment : str, optional
            Comment for ELog

        post: bool, optional
            Whether to post to the experimental ELog or not. Will not post if
            not recording

        Note
        ----
        """

        comment = comment or ''
        # Start recording
        logger.info("Starting DAQ run, -> record=%s", record)
        daq.begin(events=events, record=record)
        time.sleep(1)
        # Post to ELog if desired
        runnum = daq._control.runnumber()
        info = [runnum, comment, events, self._delaystr]
        post_msg = post_template.format(*info)
        print(post_msg)
        if post and record:
            elog(msg=post_msg, run=runnum)

        # Wait for the DAQ to finish
        logger.info("Waiting or DAQ to complete %s events ...", events)
        daq.wait()
        logger.info("Run complete!")
        daq.end_run()
        time.sleep(0.5)
        return


    def continuous_ccmscan(self,energies, pointTime=1, move_vernier=True, bidirectional=False, kill=True, beam_check = False):
        #Set to go up and down once.
        initial_energy=ccm.E_Vernier.position
        try:
            for E in energies:
                if beam_check:
                    while caget('XCS:SB1:BMMON:SUM')< 100:
                        time.sleep(1.0)
                        print('beam down. Scan paused.')
                if move_vernier:
                    ccm.E_Vernier.move(E, kill=kill)
                else:
                    ccm.E.move(E, kill=kill)
                time.sleep(pointTime)
            if bidirectional:
                for E in energies[::-1]:
                    if beam_check:
                        while caget('XCS:SB1:BMMON:SUM')< 100:
                            time.sleep(1.0)
                            print('beam down. Scan paused.')
                    if move_vernier:
                        ccm.E_Vernier.move(E, kill=kill)
                    else:
                        ccm.E.move(E, kill=kill)
                    time.sleep(pointTime)
        except KeyboardInterrupt:
                print(f'Scan end signal received. Returning ccm to energy before scan: {initial_energy}')
                ccm.E_Vernier.move(initial_energy, kill=False)
        finally:
            if move_vernier:
                ccm.E_Vernier.move(initial_energy, kill=kill)
            else:
                ccm.E.move(initial_energy, kill=kill)
            time.sleep(pointTime)


    def perform_run_with_escan(self, energies, record=True, comment='', pointTime=1,
                                 post=True, move_vernier=True,bidirectional=False, beam_check=False,
                    **kwargs):
        """
        Perform a single run of the experiment

        Parameters
        ----------
        energies: List[float] a list of energies to scan over

        record: bool, optional
            Whether to record the run

        comment : str, optional
            Comment for ELog

        pointTime : int, optional
            how long in seconds to wait at a given energy before moving

        post: bool, optional
            Whether to post to the experimental ELog or not. Will not post if
            not recording

        move_vernier: bool, optional
            Whether or not to move the vernier while scanning the channel cut mono.
        
        beam_check: bool, optional, default False
            Whether to check for ipm4 counts before moving to the next step of the ccm scan. Pauses if the beam drops.
        
        Note
        ----
        """

        # Create descriptive message
        comment = comment or ''
        logger.info("Starting DAQ run, -> record=%s", record)
        #daq.disconnect()
        daq.configure()
        try:
            #start DAQ, then start scanning
            daq.begin(record=record) #note we do not specify # of events, so it records until we stop
            # Post to ELog if desired
            runnum = daq._control.runnumber()
            #info = [runnum, comment, self._delaystr, min(energies), max(energies)]
            #post_msg = post_template_escan.format(*info)
            time.sleep(1) # give DAQ a second
           #print(post_msg)
           # if post and record:
           #     elog.post(msg=post_msg, run=runnum)
            #now start scanning
            self.continuous_ccmscan(energies, pointTime=pointTime, move_vernier=move_vernier,bidirectional=bidirectional,beam_check=beam_check)
        except KeyboardInterrupt:
            print('Interrupt signal received. Stopping run and DAQ')
        finally: 
            daq.end_run()
            logger.info("Run complete!")
            #daq.disconnect()
        
#    def perform_run_with_escan_test(self, energies, record=True, comment='', pointTime=1,
#                                 post=True, move_vernier=True,bidirectional=False,
#                    **kwargs):
#
#        # Create descriptive message
#        comment = comment or ''
#        logger.info("Starting DAQ run, -> record=%s", record)
#        #daq.disconnect()
#        daq.configure()
#        try:
#            #start DAQ, then start scanning
#            daq.begin(record=record) #note we do not specify # of events, so it records until we stop
#            # Post to ELog if desired
#            runnum = daq._control.runnumber()
#            #info = [runnum, comment, self._delaystr, min(energies), max(energies)]
#            #post_msg = post_template_escan.format(*info)
#            time.sleep(1) # give DAQ a second
#           #print(post_msg)
#           # if post and record:
#           #     elog.post(msg=post_msg, run=runnum)
#            #now start scanning
#            self.continuous_ccmscan(energies, pointTime=pointTime, move_vernier=move_vernier,bidirectional=bidirectional)
#        except KeyboardInterrupt:
#            print('Interrupt signal received. Stopping run and DAQ')
#        finally: 
#            daq.end_run()
#            logger.info("Run complete!")
#            #daq.disconnect()        

    def loop(self, delays=[], nruns=1, light_events=3000, 
             dark_events=None, record=True, comment='', post=True):
        """
        Loop through a number of delays a number of times while running the DAQ
        Parameters
        ----------
        delays: list, optional
            Requested laser delays in nanoseconds
            close fs_shutter if False or None, 
            i.e., delays=[None, 1000, 1e6, 1e7] loop through:
            - close opo shutter
            - 1 us delay
            - 1 ms delay
            - 10 ms delay

        nruns: int, optional
            Number of iterations to run requested delays

        light_events: int, optional
            Number of events to sample with requested laser pulses
        dark_events: int, optional
           Number of events to sample with all lasers shuttered
        record: bool, optional
           Choice to record or not
        comment: str, optional
           Comment for ELog
        post : bool, optional
           Whether to post to ELog or not. Will not post if not recording.
        """
        
        # Accept a single int or float
        if isinstance(delays, (float, int)):
            delays = [delays]
        
        # Preserve the original state of DAQ
        logger.info("Running delays %r, %s times ...", delays, nruns)
        delays = delays or [False]
        try:
            for irun in range(nruns):
                run = irun+1
                logger.info("Beginning run %s of %s", run, nruns)
                for delay in delays:
                    if light_events:
                        # Perform the light run
                        self.perform_run(light_events,
                                         record=record,
                                         post=post, comment=comment)

                    # Perform the dark run
                    if dark_events:
                        self.perform_run(events=dark_events, record=record,
                                         post=post, comment=comment)
            logger.info("All requested scans completed!")
        except KeyboardInterrupt:
            logger.warning("Scan interrupted by user request!")
            logger.info("Stopping DAQ ...")
            daq.stop()
        
        # Return the DAQ to the original state
        finally:
            logger.info("Disconnecting from DAQ ...")
            daq.disconnect()
        return


    def loop_escan(self, energies, delays=[], nruns=1, record=True, comment='', 
                   post=True, pointTime=1, move_vernier=True):
        """
        Loop through a number of delays a number of times while running the DAQ
        Parameters
        ----------
        delays: list, optional
            Requested laser delays in nanoseconds
            close fs_shutter if False or None, 
            i.e., delays=[None, 1000, 1e6, 1e7] loop through:
            - 1 us delay
            - 1 ms delay
            - 10 ms delay

        nruns: int, optional
            Number of iterations to run requested delays

        record: bool, optional
            Whether to record the run or not
        comment: str, optional
           Comment for ELog
        post : bool, optional
           Whether to post to ELog or not. Will not post if not recording.
        pointTime: positive Number, optional
           time in seconds to dwell at a given energy before moving
        move_vernier: bool, optional
            whether to have vernier track CCM motion or not
        """
        
        # Accept a single int or float
        if isinstance(delays, (float, int)):
            delays = [delays]
        
        # Preserve the original state of DAQ
        logger.info("Running delays %r, %s times ...", delays, nruns)
        delays = delays or [False]
        try:
            for irun in range(nruns):
                run = irun+1
                logger.info("Beginning run %s of %s", run, nruns)
                for delay in delays:

                    # Perform the run
                    self.perform_run_with_escan(energies,
                                 record=record,
                                 post=post,
                                 comment=comment,
                                 pointTime=pointTime,
                                 move_vernier=move_vernier)
            logger.info("All requested scans completed!")
        except KeyboardInterrupt:
            logger.warning("Scan interrupted by user request!")
            logger.info("Stopping DAQ ...")
            daq.stop()
        
        # Return the DAQ to the original state
        finally:
            logger.info("Disconnecting from DAQ ...")
            daq.disconnect()
        return


    def dummy_daq_test(self, events=360, sleep=3, record=False):
        daq.connect()
        while 1:
            daq.begin(events=events, record=record)
            daq.wait()
            daq.end_run()
            time.sleep(sleep)
            print(time.ctime(time.time()))
        return


    def ccm_many(self, elist, pointTime=1, nRepeat=10, kill=True):
        for ii in range(nRepeat):
            print(f'Start scan {ii}')
            self.continuous_ccmscan(elist, pointTime=pointTime, kill=kill)
        return


post_template = """\
Run Number: {} {}

Acquiring {} events

{}
"""


post_template_escan = """\
Run Number: {} {}

{}
Minimum photon_energy -> {}
Maximum photon_energy -> {}
"""


class MicroToNano():
    def __init__(self):
        self._offset_nano = 0

    def setOffset_nano(self, offset):
        self._offset_nano = offset

    def setOffset_micro(self, offset):
        self._offset_nano = offset * 1000

    def getOffset_nano(self):
        return self._offset_nano

    def __call__(self, micro):
        return (micro * 1000) + self._offset_nano
