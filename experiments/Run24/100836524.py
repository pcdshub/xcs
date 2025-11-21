

from subprocess import check_output

import logging
import json
import sys
import time
import os

import numpy as np
import elog
from pcdsdevices.device_types import DCCM as dccm
from hutch_python.utils import safe_load
from ophyd import EpicsSignalRO
from ophyd import EpicsSignal
from bluesky import RunEngine
from bluesky.plans import scan, list_scan, count
from bluesky.plan_stubs import abs_set, trigger_and_read
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
from datetime import datetime

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

        with safe_load ('LED'):
            self.led = Trigger('XCS:R42:EVR:01:TRIG6', name='led_delay')
            self.led_uS = MicroToNano()


        with safe_load ('Liquid Jet Epix Detector Motors'):
            det_x = Newport('XCS:USR:MMN:08', name='det_x')
            det_y = IMS('XCS:USR:MMN:33', name='det_y')
            det_z = Newport('XCS:USR:MMN:16', name='det_z')

        with safe_load('Von Hamos Beckhoff'):
            from ophyd.device import Device, Component as Cpt
            from pcdsdevices.epics_motor import BeckhoffAxis                                                 
            class VonHamos_Spec(Device):                                                                     
                cr1_tilt = Cpt(BeckhoffAxis, ':10', name='cr1_tilt')                                         
                cr2_tilt = Cpt(BeckhoffAxis, ':11', name='cr2_tilt')                                         
                cr3_tilt = Cpt(BeckhoffAxis, ':12', name='cr3_tilt')
                cr4_tilt = Cpt(BeckhoffAxis, ':13', name='cr4_tilt')
                cr1_move = Cpt(BeckhoffAxis, ':02', name='cr1_move')
                cr2_move = Cpt(BeckhoffAxis, ':03', name='cr2_move')
                cr3_move = Cpt(BeckhoffAxis, ':04', name='cr3_move')                                         
                cr4_move = Cpt(BeckhoffAxis, ':05', name='cr4_move')                                         
                cr1_rot = Cpt(BeckhoffAxis, ':06', name='cr1_rot')                                           
                cr2_rot = Cpt(BeckhoffAxis, ':07', name='cr2_rot')                                           
                cr3_rot = Cpt(BeckhoffAxis, ':08', name='cr3_rot')                                           
                cr4_rot = Cpt(BeckhoffAxis, ':09', name='cr4_rot')                                           
                com_rot = Cpt(BeckhoffAxis, ':01', name='com_rot')
            self.vhs = VonHamos_Spec('MFX:VHS:MMB', name='vhs')

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
    
    #labmax=EpicsSignal('XCS:LPW:01:DATA_PRI')    
    #import databroker
    #from databroker import temp
    def knife_edge(self,det,motor,start,stop,steps,n,guess): #n=#of measurements at each step
        from databroker import Broker
        import numpy as np
        from scipy.optimize import minimize
        import matplotlib.pyplot as plt
        from bluesky.preprocessors import run_decorator
        from ophyd.signal import EpicsSignal
        from bluesky.plan_stubs import abs_set
        from bluesky.callbacks.best_effort import BestEffortCallback
        from scipy import special
        from scipy.optimize import curve_fit
        from scipy.special import erfc

        print("Doing knife edge laser scan on motor:", motor)
        ljh_jet_x=EpicsSignal('XCS:LJH:JET:X')
        labmax=EpicsSignal('XCS:LPW:01:DATA_PRI')

        #RE(scan([labmax], motor, start, stop, steps)) #, per_step=num_measurements)
        positions = np.repeat(np.linspace(start,stop,steps),n)
        #positions = [1,2,3,4,5]
        print("positions",positions)
        
        RE = RunEngine()
        db = Broker.named('temp')
        RE.subscribe(db.insert)
        
        det_arr = []

        def labmax_range_scan(detector, motor, positions):
            for pos in positions:
                print("pos", pos)
                
                # Move motor to the next position
                yield from abs_set(ljh_jet_x, pos, wait=True)
        
                # Trigger the detector and read its value
                print("trigger the detector and read it's value")
                yield from count([detector])
                det_value = list(detector.read().values())[0]['value']
        
                # Apply conditional logic based on detector value using epics.caput
                if det_value < 3e-06:
                    # Set detector to setting A using caput (e.g., change some configuration)
                    print("det_value <", det_value)
                    os.system('caput XCS:LPW:01:SETRANGE 3e-06')
                else:
                    # Set detector to setting B using caput (e.g., change some configuration)
                    # Set labmax range                                                                                        
                    print("det_value >", det_value)
                    os.system('caput XCS:LPW:01:SETRANGE 3e-05')

                # Read the detector again after setting change
                print("reading detector again after setting change")
                yield from count([detector],num=1)
                det_value = list(detector.read().values())[0]['value']
                print("det valued read", det_value)
                det_arr.append(det_value)
                print("appended values")
            yield from list_scan([labmax], motor, positions)
            print("closing run")
    
        
        print("starting the plan")
        uids=RE(labmax_range_scan(labmax, motor, positions)) #motor
        

        header = db[uids]
        h = db[-1]
        t = h.table()
        
        #print("header.table",t)
        #print('ljh_jet_x',t['ljh_jet_x'])
        #print('det',t['XCS:LPW:01:DATA_PRI'])
        print("det_arr", det_arr)

        power = det_arr #t['XCS:LPW:01:DATA_PRI']
        position = t['ljh_jet_x']


               
        #Error function
        def error_function(x, a, b, c, d):
            #a,b,c,d = params
            return a * special.erfc(b * (x - c)) + d


        # Step 1: Create a dictionary to collect y values for each x
        xy_dict = {}

        # Step 2: Populate the dictionary
        for x, y in zip(position, power):
            if x not in xy_dict:
                xy_dict[x] = []
            xy_dict[x].append(y)

        # Step 3: Compute the averages
        x_unique = []
        y_avg = []
        
        for x in sorted(xy_dict.keys()):  # Sort keys to maintain order
            x_unique.append(x)
            y_avg.append(np.mean(xy_dict[x]))
        
    
            
        # Convert lists to numpy arrays (optional)
        pos_unique = np.array(x_unique)

        int_avg = np.array(y_avg)

        # Print the results
        print("Unique x values:", pos_unique)
        print("Averaged y values:", int_avg)

        # Fit the data to the error function model
        initial_guess_erf = [(min(int_avg)-max(int_avg))/2, 2/(min(int_avg)-max(int_avg)), np.mean(pos_unique), max(int_avg)]
        params_erf, covariance = curve_fit(error_function, pos_unique, int_avg, p0=initial_guess_erf)
        print("initial guess", initial_guess_erf)

        # Plot the original data and the fitted curve
        plt.scatter(pos_unique, int_avg, label='Data')
        plt.plot(position, error_function(position, *params_erf), color='red', label='Error Function Fit')
        plt.legend()
        plt.xlabel('position [mm]')
        plt.ylabel('power [au]')
        plt.title('Knife Edge Scan')

        
        # Extrapolating
        x_interp = np.linspace(np.min(pos_unique), np.max(pos_unique), num=100)
        y_interp = error_function(x_interp,*params_erf)


        # take derivative
        dy = -np.diff(y_interp)
        dx = x_interp[:len(dy)]
        #plt.plot(dx, dy, 'o', label='derivative')
        

        # define and fit gaussian and plot
        def gauss(x, y0, A, x0, sigma): 
            return y0 + A*np.exp(-(x-x0)**2/(2*sigma**2))

        #guess = [0, 0.03, 0.15, 0.01]
        guess = [0, np.max(dy),((np.max(dx)-np.min(dx))/2), 0.08]

        popt, pcov = curve_fit(gauss, dx, dy, p0=guess)
        FWHM = 1000*2*np.sqrt(2*np.log(2))*(popt[3])
        print("FWHM =",1000*2*np.sqrt(2*np.log(2))*(popt[3]),"um")

        plt.plot(dx,(1/np.max(abs(dy)))*gauss(dx,*popt),label='Fitted Gaussian', color='orange')
        plt.legend()
        
    
        #save the data in a file                                                                                                                              
        fwhm=np.full(shape=len(x_unique), fill_value=FWHM, dtype=np.float64)

        combined_array = np.column_stack((x_unique,y_avg,fwhm))

        # datetime object containing current date and time                                                                                                         
        now = datetime.now()
        dt_string = now.strftime("%Y%m%d_%H:%M")

        folder_path = '/cds/group/xcs/laser/'
        file_path = os.path.join(folder_path, dt_string+'.dat')
        plot_path = os.path.join(folder_path, dt_string+'_plot.png')
        np.savetxt(file_path, combined_array, delimiter=' ', fmt='%.8f')

        plt.savefig(plot_path, format="png")
        plt.show()
        print("Data/Plots saved to /cds/group/xcs/laser/")

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


    def las_check(f):
        '''wrapper to check if lp is OUT. if IN, asks for operator input'''
        def wrap(*args):
            if lp()=='IN':
                check1=input('laser shutter is IN, continue? (y/n)')
                if check1=='y':
                    return f(*args)
                else:
                    print('no scan')
            else:
                return f(*args)
        return wrap




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


    def continuous_dccmscan(self,energies, pointTime=1, move_vernier=True, bidirectional=False, beam_check = False):
        #Set to go up and down once.
        #initial_energy=ccm.E_Vernier.position
        initial_energy=dccm.energy_with_vernier.wm()
        try:
            for E in energies:
                if beam_check:
                    while caget('XCS:SB1:BMMON:SUM')< 100:
                        time.sleep(1.0)
                        print('beam down. Scan paused.')
                if move_vernier:
                    #ccm.E_Vernier.move(E, kill=kill)
                    dccm.energy_with_vernier.move(E)
                    print(f'Moving dccm.E_Vernier to {E}')
                else:
                    #ccm.E.move(E, kill=kill)
                    dccm.energy.move(E)
                    print(f'Moving dccm.E to {E}')
                time.sleep(pointTime)
            if bidirectional:
                for E in energies[::-1]:
                    if beam_check:
                        while caget('XCS:SB1:BMMON:SUM')< 100:
                            time.sleep(1.0)
                            print('beam down. Scan paused.')
                    if move_vernier:
                        dccm.energy_with_vernier.move(E)
                        print(f'Moving dccm.E_Vernier to {E}')
                    else:
                        dccm.energy.move(E)
                        print(f'Moving dccm.E to {E}')
                    time.sleep(pointTime)
        except KeyboardInterrupt:
                print(f'Scan end signal received. Returning ccm to energy before scan: {initial_energy}')
                dccm.energy_with_vernier.move(initial_energy)
                print(f'Moving dccm.E_Vernier to {initial_energy}')
        finally:
            if move_vernier:
                dccm.energy_with_vernier.move(initial_energy)
                print(f'Moving dccm.E_Vernier to initial energy {E}')
            else:
                dccm.energy.move(initial_energy)
                print(f'Moving dccm.E to initial energy {E}')
            time.sleep(pointTime)


    def perform_dccm_with_escan(self, energies, record=True, comment='', pointTime=1,
                                 post=True, move_vernier=True,bidirectional=False, beam_check=False,
                    **kwargs):
        """
        Perform a single run of the experiment

        Parameters
        ----------
        energies: List[float] a list of energies(keV) to scan over

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
            daq.begin_infinite(record=record) #note we do not specify # of events, so it records until we stop
            runnum = daq._control.runnumber()
            time.sleep(1) # give DAQ a second
            self.continuous_dccmscan(energies, pointTime=pointTime, move_vernier=move_vernier,bidirectional=bidirectional,beam_check=beam_check)
        except KeyboardInterrupt:
            print('Interrupt signal received. Stopping run and DAQ')
        finally: 
            daq.end_run()
            logger.info("Run complete!")
            #daq.disconnect()
        

    

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
