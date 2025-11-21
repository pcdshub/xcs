from subprocess import check_output

import logging
import json
import sys
import time
import os

import pickle
import numpy as np
import h5py
from hutch_python.utils import safe_load
from epics import caget, caget_many, PV
from ophyd import EpicsSignalRO
from ophyd import EpicsSignal
from bluesky import RunEngine
from bluesky.plans import scan
from bluesky.plans import list_scan, list_grid_scan
from ophyd import Component as Cpt
from ophyd import Device
from pcdsdevices.interface import BaseInterface
from pcdsdevices.areadetector import plugins
from pcdsdevices.epics_motor import SmarActTipTilt
from pcdsdevices.epics_motor import SmarActOpenLoop
from xcs.db import daq
from xcs.db import camviewer
from xcs.db import RE, seq, pp
from xcs.db import xcs_ccm as ccm
from xcs.delay_scan import delay_scan
from xcs.db import lxt_fast
from pcdsdevices.device_types import Newport, IMS
from xcs.devices import LaserShutter
from elog import HutchELog
from pcdsdevices.device_types import Trigger

from pcdsdevices.sequencer import EventSequencer
seq2 = EventSequencer('ECS:SYS0:11', name='seq_11')

#from macros import *
import time

pickle.HIGHEST_PROTOCOL = 4
import pandas as pd

logger = logging.getLogger(__name__)

## XY Grid Scan
from pcdsdevices.targets import XYGridStage
from xcs.db import RE, bpp, bps, seq, xcs_gon, gon_sy, lp
from xcs.db import xcs_pulsepicker as pp
import time

# sample file location for the grid
grid_filepath = '/cds/home/opr/xcsopr/experiments/xcslw6819/' 
if not os.path.exists(grid_filepath):
    open(grid_filepath, 'a').close()


def get_run():
    run_number = check_output('get_lastRun').decode('utf-8').replace('\n','')
    return run_number

class User():
    def __init__(self):
        self._sync_markers = {0.5:0, 1:1, 5:2, 10:3, 30:4, 60:5, 120:6, 360:7}
        with safe_load('Spare Event Sequencer'):
            self.seq2 = EventSequencer('ECS:SYS0:11', name='seq_11')
        with safe_load('PP trigger'):
            self.evr_pp = Trigger('XCS:USR:EVR:TRIG1', name='evr_pp')
        with safe_load('SmarAct'):
            self.las1 = SmarActTipTilt(prefix='XCS:MCS2:01', tip_pv=':m1', tilt_pv=':m2', name='las1')
            self.las2 = SmarActTipTilt(prefix='XCS:MCS2:01', tip_pv=':m4', tilt_pv=':m5', name= 'las2')
            self.las3 = SmarActTipTilt(prefix='XCS:MCS2:01', tip_pv=':m7', tilt_pv=':m8', name = 'las3')

#        with safe_load('elog'):
#            kwargs = dict()
#            self.elog = HutchELog.from_conf('XCS', **kwargs)
#

        with safe_load('lw68_motors'):
            self.iStar_focus = Newport('XCS:USR:MMN:06', name='iStar_focus')
            self.bbo_wp = Newport('XCS:USR:MMN:07', name='bbo_wp')
            self.huber_x = IMS('XCS:USR:MMS:40', name='huber_x')
            self.huber_y = IMS('XCS:USR:MMS:37', name='huber_y')
            self.ldx = IMS('XCS:LAM:MMS:06',name='ldx')
            self.ldy = IMS('XCS:LAM:MMS:07',name='ldy')
            self.bs6x = IMS('XCS:LAM:MMS:11',name='bs6x')
            self.bs6y = IMS('XCS:LAM:MMS:12',name='bs6y')
            self.att = IMS('XCS:SB2:MMS:15', name='att'); # need to chose one ATT motor that does the desired attenuation and identify the two positions to go just in/out. Motor 15 is the 320um filter which does about a factor of 10.
  

        with safe_load('Triggers'):
            self.gateEVR = Trigger('XCS:R42:EVR:01:TRIG4', name='evr_trig4')
            self.gateEVR_ticks = EpicsSignal('XCS:R42:EVR:01:CTRL.DG4D', name='evr_trig4_ticks')
            self.GD = self.gateEVR.ns_delay
        self.tx = self.huber_y
        self.ty = gon_sy
        self.tn = self.huber_x
        #self.ty = xcs_gon.ver 
        self.lp = LaserShutter('XCS:USR:ao1:7', name='lp')

    
    ######################################################3
    # Fixed Target Scanning and control
    
    def init_target_grid(self, m, n, sample_name):
        xy = XYGridStage(self.tx, self.ty, m, n, grid_filepath)
        xy.set_presets()
        xy.map_points()
        xy.save_grid(sample_name)
        xy.current_sample = sample_name
        self.xy = xy

    def load_sample_grid(self, sample_name):
        self.xy.load_sample(sample_name)
        self.xy.map_points()




    # Diling's lazy function for close packing with offsetted rows
    # modified by Tyler and Vincent for professionalism   
    @bpp.run_decorator()
    def gridScan_old(self, motor, posList, sample, iRange, jRange, deltaX):
        iRange = list(iRange)
        jRange = list(jRange)
        if len(posList) != len(iRange):
            print('number of scan steps not matching grid total row number, abort.')
        else:
            xs, ys = self.xy.compute_mapped_point(1,1, compute_all=True) # get all positions
            s_shape = self.xy.get_sample_map_info(sample)
            s_shape = (s_shape[0], s_shape[1])
            for ni,i in enumerate(iRange):
                motor.umv(posList[ni])
                jRange_thisRow = jRange
                #if np.mod(ind, 2)==1:
                    #jRange_thisRow.reverse()
                for j in jRange_thisRow:
                    idx = np.ravel_multi_index([i,j], s_shape) # find raveled index from 2d coord i,j
                    x_pos = xs[idx]
                    y_pos = ys[idx]
                    #x_pos,y_pos = self.xy.compute_mapped_point(i, j, compute_all=False)
                    if np.mod(i,2)==1:
                        y_pos = y_pos+deltaX
                    yield from bps.mv(self.xy.x, x_pos, self.xy.y, y_pos)
                    yield from bps.trigger_and_read([seq, self.xy.x, self.xy.y])
                    time.sleep(0.2)
                    while seq.play_status.get() == 2: continue
                jRange.reverse()

    @bpp.run_decorator()
    def gridScan(self, motor, posList, sample, iRange, jRange, deltaX, snake=True):
        iRange = list(iRange)
        jRange = list(jRange)
        if len(posList) != len(iRange):
            print('number of scan steps not matching grid total row number, abort.')
        else:
            self.xy.load(sample)
            for ni,i in enumerate(iRange):
                motor.umv(posList[ni])
                jRange_thisRow = jRange
                for j in jRange_thisRow:
                    x_pos,y_pos = self.xy.compute_mapped_point(i, j, sample, compute_all=False)
                    if np.mod(i,2)==1:
                        x_pos = x_pos+deltaX
                    yield from bps.mv(self.xy.x, x_pos, self.xy.y, y_pos)
                    yield from bps.trigger_and_read([seq, self.xy.x, self.xy.y])
                    time.sleep(0.1)
                    while seq.play_status.get() == 2: continue
                if snake:
                    jRange.reverse()
    
    @bpp.run_decorator()
    def gridScanAtt(self, motor, posList, sample, iRange, jRange, deltaX, snake=True):
        InPosition = 12;
        OutPosition = 10;
        iRange = list(iRange)
        jRange = list(jRange)

        self.att.mv(InPosition)
        if len(posList) != len(iRange):
            print('number of scan steps not matching grid total row number, abort.')
        else:
            self.xy.load(sample)
            for ni,i in enumerate(iRange):
                motor.umv(posList[ni])
                jRange_thisRow = jRange
                for j in jRange_thisRow:
                    x_pos,y_pos = self.xy.compute_mapped_point(i, j, sample, compute_all=False)
                    if np.mod(i,2)==1:
                        x_pos = x_pos+deltaX
                    yield from bps.mv(self.xy.x, x_pos, self.xy.y, y_pos)
                    self.att.mv(InPosition)
                    self.att.wait()
                    seq2.start()
                    time.sleep(0.1)
                    while seq2.play_status.get() == 2: continue
                    self.att.mv(OutPosition)
                    self.att.wait()
                    yield from bps.trigger_and_read([seq, self.xy.x, self.xy.y])
                    #seq.start()
                    time.sleep(0.1)
                    while seq.play_status.get() == 2: continue
                if snake:
                    jRange.reverse()


    def gridScan_Daq(self, motor, posList, sample, iRange, jRange, deltaX, snake=True):
        plan = self.gridScan(motor, posList, sample, iRange, jRange, deltaX, snake)
        try:
            daq.disconnect()
        except:
            print('DAQ might be disconnected already')
        daq.connect()
        daq.begin()
        RE(plan)
        daq.end_run()

    def gridScanAtt_Daq(self, motor, posList, sample, iRange, jRange, deltaX, snake=True):
        plan = self.gridScanAtt(motor, posList, sample, iRange, jRange, deltaX, snake)
        try:
            daq.disconnect()
        except:
            print('DAQ might be disconnected already')
        daq.connect()
        daq.begin()
        RE(plan)
        daq.end_run()

    # to help move quickly between 120Hz CW mode for 
    # alignment and TT checking and single shot mode
    def go120Hz(self):
        try:
            daq.disconnect()
        except:
            print('DAQ might already be disconnected')
        lp('IN')
        pp.open()
        sync_mark = int(self._sync_markers[120])
        seq.sync_marker.put(sync_mark)
        seq.play_mode.put(2)
        shot_sequence=[]
        shot_sequence.append([85,0,0,0])
        shot_sequence.append([87,0,0,0])
        seq.sequence.put_seq(shot_sequence) 
        time.sleep(0.5)
        seq.start()
        #daq.connect()
        #daq.begin_run(record=False)

    def goSS(self, nPre=20, nOn=1, nPost=20):
        #daq.end_run()
        #daq.disconnect()
        pp.flipflop()
        self.prepare_seq(nPre, nOn, nPost)
        time.sleep(0.2)
        lp('OUT')

    # setup sparesequencer for off-on-off series
    def prepare_seq(self, nShotsPre=30, nShotsOn=1, nShotsPost=30, seqHere=seq, nBuff=1):
        ## Setup sequencer for requested rate
        #sync_mark = int(self._sync_markers[self._rate])
        #leave the sync marker: assume no dropping.
        sync_mark = int(self._sync_markers[10])
        seqHere.sync_marker.put(sync_mark)
        seqHere.play_mode.put(0) # Run sequence once
        pp.flipflop()
        #seq.play_mode.put(1) # Run sequence N Times
        #seq.rep_count.put(nshots) # Run sequence N Times
    
        ppLine = [84, 2, 0, 0]
        daqLine = [85, 2, 0, 0]
        preLine = [190, 0, 0, 0]
        onLine = [87, 0, 0, 0]
        postLine = [193, 0, 0, 0]
        bufferLine = [85, 1, 0, 0] # line to avoid falling on the parasitic 10Hz from TMO

        shot_sequence=[]
        #enable bufferline will help with the soft 10Hz multiplexing case
        #for buff in np.arange(nBuff):
        #    shot_sequence.append(bufferLine)
        for preShot in np.arange(nShotsPre):
            shot_sequence.append(ppLine)
            shot_sequence.append(daqLine)
            shot_sequence.append(preLine)
        for onShot in np.arange(nShotsOn):
            shot_sequence.append(ppLine)
            shot_sequence.append(daqLine)
            shot_sequence.append(onLine)
        for postShot in np.arange(nShotsPost):
            shot_sequence.append(ppLine)
            shot_sequence.append(daqLine)
            shot_sequence.append(postLine)

        #logging.debug("Sequence: {}".format(shot_sequence))                  
        seqHere.sequence.put_seq(shot_sequence) 
    
    # put pulse picker to flip flop mod
    def set_pp_flipflop(self):
        burstdelay=4.5e-3*1e9 # not needed here
        flipflopdelay=8e-3*1e9
        followerdelay=3.8e-5*1e9 # not needed here
        self.evr_pp.ns_delay.set(flipflopdelay) # evr channel needs to be defined
        pp.flipflop(wait=True)


    ######################################################

    def takeRun(self, nEvents, record=None, use_l3t=False):
        daq.configure(events=120, record=record, use_l3t=use_l3t)
        daq.begin(events=nEvents)
        daq.wait()
        daq.end_run()

    def ascan(self, motor, start, end, nsteps, nEvents, record=None, use_l3t=False, post=False):
        self.cleanup_RE()
        currPos = motor.wm()
        daq.configure(nEvents, record=record, controls=[motor], use_l3t=use_l3t)
        try:
            RE(scan([daq], motor, start, end, nsteps))
        except Exception:
            logger.debug('RE Exit', exc_info=True)
        finally:
            self.cleanup_RE()
        if post:
            run = get_run()
            message = 'scan {name} from {min1:.3f} to {max1:.3f} in {num1} steps'.format(name=motor.name,
                        min1=start,max1=end,
                        num1=nsteps)

            self.elog.post(message,run=int(run))

        motor.mv(currPos)
    def pv_ascan(self, signal, start, end, nsteps, nEvents, record=None, use_l3t=False, post=False):
        self.cleanup_RE()
        currPos = signal.get()
        #signal.put_complete = True
        daq.configure(nEvents, record=record, controls=[signal], use_l3t=use_l3t)
        try:
            RE(scan([daq], signal, start, end, nsteps))
        except Exception:
            logger.debug('RE Exit', exc_info=True)
        finally:
            self.cleanup_RE()

        signal.put(currPos)
        currPos = signal.get()

        if post:
            run = get_run()
            message = 'scan {name} from {min1:.3f} to {max1:.3f} in {num1} steps'.format(name=signal.name,
                        min1=start,max1=end,
                        num1=nsteps)
            self.elog.post(message,run=int(run))

    def listscan(self, motor, posList, nEvents, record=None, use_l3t=False, post=False):
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

        if post:
            run = get_run()
            message = 'scan {name} from {min1:.3f} to {max1:.3f} in {num1} steps'.format(name=motor.name,
                        min1=posList[0],max1=posList[-1],
                        num1=posList.size)
            self.elog.post(message,run=int(run))




    def pv_dscan(self, signal, start, end, nsteps, nEvents, record=None, use_l3t=False, post=False):
        self.cleanup_RE()
        daq.configure(nEvents, record=record, controls=[signal], use_l3t=use_l3t)
        currPos = signal.get()
        try:
            RE(scan([daq], signal, currPos+start, currPos+end, nsteps))
        except Exception:
            logger.debug('RE Exit', exc_info=True)
        finally:
            self.cleanup_RE()
        signal.put(int(currPos))

        if post:
            run = get_run()
            message = 'scan {name} from {min1:.3f} to {max1:.3f} in {num1} steps'.format(name=signal.name,
                        min1=start+currPos,max1=end+currPos,
                        num1=nsteps)
            self.elog.post(message,run=int(run))

    def d2scan(self, m1, a1, b1, m2, a2, b2, nsteps, nEvents, record=True, use_l3t=False, post=False):
        currPos1 = m1.wm()
        currPos2 = m2.wm()
       
        # just use a2scan
        self.a2scan(m1, currPos1+a1, currPos1+b1, m2, currPos2+a2, currPos2+b2, nsteps, nEvents, record=record, use_l3t=use_l3t, post=post)

    def a2scan(self, m1, a1, b1, m2, a2, b2, nsteps, nEvents, record=True, use_l3t=False, post=False):

        currPos1 = m1.wm()
        currPos2 = m2.wm()

        self.cleanup_RE()
        daq.configure(nEvents, record=record, controls=[m1, m2], use_l3t=use_l3t)
        try:
            RE(scan([daq], m1, a1, b1, m2, a2, b2, nsteps))
        except Exception:
            logger.debug('RE Exit', exc_info=True)
        finally:
            self.cleanup_RE()

        # move motors back to starting position
        m1.mv(currPos1)
        m2.mv(currPos2)

        if post:
            run = get_run()

            message = f'scan {m1.name} from {a1:.3f} to {b1:.3f} and {m2.name} from {a2:.3f} to {b2:.3f} in {nsteps} steps'
            self.elog.post(message,run=int(run))



    def a3scan(self, m1, a1, b1, m2, a2, b2, m3, a3, b3, nsteps, nEvents, record=True, post=False):
        self.cleanup_RE()
        daq.configure(nEvents, record=record, controls=[m1, m2, m3])
        try:
            RE(scan([daq], m1, a1, b1, m2, a2, b2, m3, a3, b3, nsteps))
        except Exception:
            logger.debug('RE Exit', exc_info=True)
        finally:
            self.cleanup_RE()

    def delay_scan(self, start, end, sweep_time, record=None, use_l3t=False,
                   duration=None, post=False):
        """Delay scan with the daq."""
        self.cleanup_RE()
        daq.configure(events=None, duration=None, record=record, use_l3t=use_l3t, controls=[lxt_fast])
        try:
            RE(delay_scan(daq, lxt_fast, [start, end], sweep_time,
                          duration=duration))
        except Exception:
            logger.debug('RE Exit', exc_info=True)
        finally:
            self.cleanup_RE()

        if post:
            run = get_run()
            message = 'delay scan from {min1:.2f} to {max1:.2f} in with {sweep:.2f}s sweep time'.format(min1=start,max1=end,
                        sweep=sweep_time)
            self.elog.post(message,run=int(run))


  
