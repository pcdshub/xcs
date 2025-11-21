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

from bluesky.plans import list_scan

class User():
    def __init__(self):
        self._sync_markers = {0.5:0, 1:1, 5:2, 10:3, 30:4, 60:5, 120:6, 360:7}
        self.delay = EpicsSignal('XCS:MOB:DDG:01:aDelayAO')
        self.delay_galvo = EpicsSignal('XCS:MOB:DDG:01:cDelayAO')

    def go120Hz(self):
        shot_sequence=[]
        shot_sequence.append([85,0,0,0])
        seq.sequence.put_seq(shot_sequence)

    def prepare_seq(self, nShots=1, nBuff=118):
        ##nBuff=118 for Icarus(1Hz), nBuff=10 for Zyla (10Hz) 
        ## Setup sequencer for requested rate
        #sync_mark = int(self._sync_markers[self._rate])
        #leave the sync marker: assume no dropping.
        sync_mark = int(self._sync_markers[10])
        seq.sync_marker.put(sync_mark)
        #seq.play_mode.put(0) # Run sequence once
        seq.play_mode.put(1) # Run sequence N Times
        seq.rep_count.put(nShots) # Run sequence N Times

        buff = [0, nBuff, 0, 0] #Event code, dBeam, dFiducial, burst count
        ppLine = [84, 0, 0, 0] #pulse picker
        daqLineOff = [85, 2, 0, 0] #daq not recording
        daqLineOn = [85, 1, 0, 0] #daq recording
        laser = [83, 1, 0, 0] #heating laser turn on
        laserMarker = [87, 0, 0, 0] #time marker that heating laser hitting sample

        shot_sequence = []
        shot_sequence.append(buff)
        shot_sequence.append(ppLine)
        shot_sequence.append(daqLineOff)
        shot_sequence.append(buff)
        shot_sequence.append(ppLine)
        shot_sequence.append(laser)
        shot_sequence.append(daqLineOn)
        shot_sequence.append(laserMarker)

        seq.sequence.put_seq(shot_sequence)
        return
    def prepare_seq2(self, nShots=1, nBuff=118, shotsBefore=1):
        ##nBuff=118 for Icarus(1Hz), nBuff=10 for Zyla (10Hz) 
        ## Setup sequencer for requested rate
        #sync_mark = int(self._sync_markers[self._rate])
        #leave the sync marker: assume no dropping.
        sync_mark = int(self._sync_markers[10])
        seq.sync_marker.put(sync_mark)
        #seq.play_mode.put(0) # Run sequence once
        seq.play_mode.put(1) # Run sequence N Times
        seq.rep_count.put(nShots) # Run sequence N Times

        buff = [0, nBuff, 0, 0] #Event code, dBeam, dFiducial, burst count
        ppLine = [84, 0, 0, 0] #pulse picker
        daqLineOff = [85, 2, 0, 0] #daq not recording
        daqLineOn = [85, 1, 0, 0] #daq recording
        laser = [83, 1, 0, 0] #heating laser turn on
        laserMarker = [87, 0, 0, 0] #time marker that heating laser hitting sample

        shot_sequence = []
        for i in range(shotsBefore):
            shot_sequence.append(buff)
            shot_sequence.append(ppLine)
            shot_sequence.append(daqLineOff)
        shot_sequence.append(buff)
        shot_sequence.append(ppLine)
        shot_sequence.append(laser)
        shot_sequence.append(daqLineOn)
        shot_sequence.append(laserMarker)

        seq.sequence.put_seq(shot_sequence)
        return

    def prepare_seq3(self, nShots=1, nBuff=118, shotsBefore=1):  
        ##Added additional delay after laser fires
        ##nBuff=118 for Icarus(1Hz), nBuff=10 for Zyla (10Hz)                                                                             
        ## Setup sequencer for requested rate                                                                                            
        #sync_mark = int(self._sync_markers[self._rate])                                                                                 
        #leave the sync marker: assume no dropping.                                                                                       
        sync_mark = int(self._sync_markers[10])
        seq.sync_marker.put(sync_mark)
        #seq.play_mode.put(0) # Run sequence once                                                                                         
        seq.play_mode.put(1) # Run sequence N Times                                                                                       
        seq.rep_count.put(nShots) # Run sequence N Times                                                                                  
        
        buff = [0, nBuff-1, 0, 0] #Event code, dBeam, dFiducial, burst count                                                                     
        ppLine = [84, 0, 0, 0] #pulse picker                                                                                              
        daqLineOff = [85, 2, 0, 0] #daq not recording                                                                                     
        daqLineOn = [85, 1, 0, 0] #daq recording                                                                                          
        laser = [83, 1, 0, 0] #heating laser turn on                                                                                      
        laserMarker = [87, 0, 0, 0] #time marker that heating laser hitting sample                                                        
        blank = [0, 1, 0, 0] #delay after heating laser turned on

        shot_sequence = []
        for i in range(shotsBefore):
            shot_sequence.append(buff)
            shot_sequence.append(blank)
            shot_sequence.append(ppLine)
            shot_sequence.append(daqLineOff)
        
        shot_sequence.append(buff)
        shot_sequence.append(laser)
        shot_sequence.append(ppLine)
        shot_sequence.append(blank)
        shot_sequence.append(daqLineOn)
        shot_sequence.append(laserMarker)

        seq.sequence.put_seq(shot_sequence)
        return



    def scan_with_delay(self, *args):

        try:
            daq.disconnect()
        except:
            print('DAQ might already be disconnected')
        daq.connect()
        daq.begin()

        RE(list_scan([seq], *args))

    def scan_daq(self, sc_x, posList):
        try:
            daq.disconnect()
        except:
            print('DAQ might already be disconnected')
        daq.connect()
        daq.begin()
        RE(bp.list_scan([seq], sc_x, [0,1,2,3]))
        daq.end_run()
