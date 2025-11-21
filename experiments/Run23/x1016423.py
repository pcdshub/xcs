

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
from xcs.db import seq
from xcs.delay_scan import delay_scan
from xcs.db import lxt_fast, lxt_fast_enc
from pcdsdevices.device_types import Newport, IMS
from pcdsdevices.evr import Trigger
from epics import caget 


import time

logger = logging.getLogger(__name__)

from pcdsdevices.evr import Trigger


#######################
class User:
    """Generic User Object"""
    with safe_load('Dummy'):
        print('Import dummy')

    def __init__(self):
        self._sync_markers = {0.5:0, 1:1, 5:2, 10:3, 30:4, 60:5, 120:6, 360:7}

        with safe_load ('LED'):
            self.led = Trigger('XCS:R42:EVR:01:TRIG6', name='led_delay')
            self.led_uS = MicroToNano()

    def go120Hz(self):
        shot_sequence=[]
        shot_sequence.append([85,0,0,0])
        seq.sequence.put_seq(shot_sequence)

    def pp_seq(self, nShots=3, nBursts=1):
        ppTrigDelay = EpicsSignal("XCS:USR:EVR:TRIG1:TDES",name="trigDelay")
        ppTrigDelay.set(4.5e6)
        ##nBuff=118 for Icarus(1Hz), nBuff=10 for Zyla (10Hz)                                                                                     
        ## Setup sequencer for requested rate                                                                                                     
        #sync_mark = int(self._sync_markers[self._rate])                                                                                          
        #leave the sync marker: assume no dropping.                                                                                                             
        sync_mark = int(self._sync_markers[10])
        seq.sync_marker.put(sync_mark)
        #seq.play_mode.put(0) # Run sequence once                                                                                                
        seq.play_mode.put(1) # Run sequence N Times                                                     
        seq.rep_count.put(nBursts) # Run sequence N Times      
        #seq.play_mode.put(1) # Run sequence N Times                                                                                                          
       
        #buff = [0, 118, 0, 0] #Event code, dBeam, dFiducial, burst count
        ppOpen = [83, 2, 0, 0] #pulse picker is open
        ppLine = [84, 0, 0, 0] #pulse picker trigger
        daqNow = [85, 0, 0,0 ]
        daqLine = [85, 1, 0, 0] # DAQ readout
        
        shot_sequence = []
        # Option 1 daq readout setup on code 85
        shot_sequence.append(ppLine)
        shot_sequence.append(ppOpen)
        shot_sequence.append(daqNow)
       
        for i in range(nShots-2):
            shot_sequence.append(daqLine)
        shot_sequence.append(ppLine)
        shot_sequence.append(daqLine)

        # Option 2 daq in running in background on event code 40
        #shot_sequence.append(ppLine)
        #shot_sequence.append(ppOpen)
        #shot_sequence.append([0, nShots-1, 0, 0])
        #shot_sequence.append(ppLine)
        ##shot_sequence.append(ppClose)

        seq.sequence.put_seq(shot_sequence)
        return



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

    def takeRun(self, nEvents=None, duration=None, record=True, use_l3t=False):
        daq.configure(events=120, record=record, use_l3t=use_l3t)
        daq.begin(events=nEvents, duration=duration)
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
                    print(f'Moving ccm.E_Vernier to {E}')
                else:
                    ccm.E.move(E, kill=kill)
                    print(f'Moving ccm.E to {E}')
                time.sleep(pointTime)
            if bidirectional:
                for E in energies[::-1]:
                    if beam_check:
                        while caget('XCS:SB1:BMMON:SUM')< 100:
                            time.sleep(1.0)
                            print('beam down. Scan paused.')
                    if move_vernier:
                        ccm.E_Vernier.move(E, kill=kill)
                        print(f'Moving ccm.E_Vernier to {E}')
                    else:
                        ccm.E.move(E, kill=kill)
                        print(f'Moving ccm.E to {E}')
                    time.sleep(pointTime)
        except KeyboardInterrupt:
                print(f'Scan end signal received. Returning ccm to energy before scan: {initial_energy}')
                ccm.E_Vernier.move(initial_energy, kill=False)
                print(f'Moving ccm.E_Vernier to {initial_energy}')
        finally:
            if move_vernier:
                ccm.E_Vernier.move(initial_energy, kill=kill)
                print(f'Moving ccm.E_Vernier to {E}')
            else:
                ccm.E.move(initial_energy, kill=kill)
                print(f'Moving ccm.E to {E}')
            time.sleep(pointTime)


    def perform_run_with_escan(self, energies, record=True, comment='', pointTime=1,
                                 post=True, move_vernier=True,bidirectional=False, beam_check=False,
                    **kwargs):
        """
        Perform a single run of the experiment

        Parameters
        ----------
        energies: List[float] a list of energies to scan over

        record: bool, optional              Whether to record the run

        comment : str, optional             for ELog

        pointTime : int, optional           long in seconds to wait at a given energy before moving

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
            daq.begin_infinite(record=record) #note we do not specify # of events, so it records until we stop
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
