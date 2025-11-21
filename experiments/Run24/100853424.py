import numpy as np
import logging
import time

from ophyd import EpicsSignal, EpicsSignalRO
from ophyd.device import Component as Cpt

from pcdsdevices.sim import FastMotor, SlowMotor
from pcdsdevices.device_types import Trigger
from pcdsdevices.device_types import IMS, Newport
from collections import namedtuple
#from pcdsdevices.targets import XYGridStage

from xcs.db import RE, bpp, bps, seq
from xcs.db import daq
from xcs.db import xcs_pulsepicker as pp
from xcs.db import dccm
from xcs.db import lxt_ttc
from typing import Tuple, List
from pcdsdevices.pseudopos import (PseudoPositioner, PseudoSingleInterface, pseudo_position_argument, real_position_argument)


sim_x = SlowMotor(name='x')
sim_y = SlowMotor(name='y')
sim_z = SlowMotor(name='z')
sim_ttc = SlowMotor(name='ttc')
sim_dccm = SlowMotor(name='dccm')

sam_x = Newport(name='sam_x', prefix='XCS:USR:MMN:08')
sam_y = IMS(name='sam_y', prefix='XCS:GON:MMS:09')
sam_z = IMS(name='sam_z', prefix='XCS:GON:MMS:08')

grid_filepath = '/cds/home/opr/xcsopr/experiments/xcs100846924/'

class User():
    def __init__(self):
        self._sync_markers = {0.5:0, 1:1, 5:2, 10:3, 30:4, 60:5, 120:6, 360:7}
        self.sam_x = sam_x
        self.sam_y = sam_y
        self.sam_z = sam_z
        self.lxt_ttc = lxt_ttc
        self.dccm = dccm
        # pp trigger
        self.evr_pp = Trigger('XCS:USR:EVR:TRIG1', name='evr_pp')
        self.theta = 22
        self.target_vertical = TargetVertical()
        self.v_pos = self.target_vertical.v_pos

    # ######### Sequencer and pulse picker ################################
    def prepare_burst(self, nShots):
        self.clear_sequence()
        print('cleared sequence')
        self.set_pp_burst()
        print('set pp flipflop')
        sync_mark = int(self._sync_markers[120])
        seq.sync_marker.put(sync_mark)
        print('set sync markers')
        seq.play_mode.put(0)
        print('running sequence once')

        ppLine = [84, 2, 0, 0]
        daqLine = [85, 2, 0, 0]
        onLine = [88, 0, 0, 0]
        
        shot_sequence = []
                

    
    def prepare_sequence(self, nShotsPre=1, nShotsOn=1, nShotsPost=0):
        # Setup sequencer
        self.clear_sequence()
        print("cleared sequence")
        self.set_pp_flipflop()
        print("set pp flipflop")
        sync_mark = int(self._sync_markers[120])
        seq.sync_marker.put(sync_mark)
        print("set sync markers")
        seq.play_mode.put(0) # Run sequence once
        print("running sequence once")
        #seq.play_mode.put(1) # Run sequence N Times
        #seq.rep_count.put(nshots) # Run sequence N Times

        ppLine = [84, 2, 0, 0]  # 2 delta beams for multiple pre-shots
        daqLine = [85, 2, 0, 0]  # always wait 2 for the pulse-picker to open
        preLine = [87, 0, 0, 0]  # marker for shot with no laser
        onLine = [88, 0, 0, 0]  # laser on-demand
        postLine = [83, 0, 0, 0]  # marker for pulses after the laser

        shot_sequence=[]
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

        #logging.info("Sequence: {}".format(shot_sequence))
        seq.sequence.put_seq(shot_sequence)
        return

    def sequence_120hz(self):
        self.clear_sequence()
        pp.close(wait=True)
        shot_sequence = [[85,0,0,0]]
        seq.sequence.put_seq(shot_sequence)
        seq.play_mode.put(2) # Play forever
        seq.start()
        return

    def clear_sequence(self):
        seq.stop()
        sequence = [[0,0,0,0]] * 200
        seq.sequence.put_seq(sequence)
        return

    def set_pp_flipflop(self):
        burstdelay = 4.5e-3*1e9 # not needed here
        flipflopdelay = 8e-3*1e9
        followerdelay = 3.8e-5*1e9 # not needed here
        self.evr_pp.ns_delay.set(flipflopdelay) # evr channel needs to be defined
        pp.flipflop(wait=True)
        return

    def set_pp_burst(self):
        burstdelay = 4.5e-3*1e9
        flipflopdelay = 8e-3*1e9
        followerdelay = 3.8e-5*1e9
        self.evr_pp.ns_delay.set(burstdelay)
        pp.burst(wait=True)

    # ######### Grid scan  ################################
    @bpp.run_decorator()
    def gridScan_xpp(self, motor, posList, sample, iRange, jRange, deltaX, snake=True):
        """
        Perform a grid scan according to a pre-defined sample grid and moves a
        given motor at each new row.

        Args:
            motor: motor to move at each new row
            posList: position list for motor.
                     Its length must match the number of rows being scanned
            sample: sample grid name
            iRange: list of row to scan
            jRange: list of column to scan
            deltaX: horizontal offset to allow close packing
            snake: if the scan must follow a snake pattern or return to the
                   first column at the end of each row
        """
        if len(posList) != len(iRange):
            print('number of scan steps not matching grid total row number, abort.')
            return

        self.xy.load(sample)
        #self.prepare_sequence(1,1,1)
        #self.xy.move_to_sample(iRange[0], jRange[0])
        iRange = list(iRange)
        jRange = list(jRange)

        for ni,i in enumerate(iRange):
            print(f'Moving to row (line) {i}.')
            motor.umv(posList[ni])
            jRange_thisRow = jRange
            for j in jRange_thisRow:
                x_pos,y_pos = self.xy.compute_mapped_point(i, j, sample,
                                                      compute_all=False)

                if np.mod(i,2)==1:
                    x_pos = x_pos+deltaX
                yield from bps.mv(self.xy.x, x_pos, self.xy.y, y_pos)
                yield from bps.trigger_and_read([seq, self.xy.x, self.xy.y])
                while seq.play_status.get() == 2: continue
            if snake:
                jRange.reverse()

    #@bpp.run_decorator()
    def grid_scan_abs(
            self,
            h_params: Tuple[float, float, float], # (start, end, stepsize)
            v_params: Tuple[float, float, float], # (start, end, stepsize)
            z_at_IP: float=0,
            dccm_energies: List = None,
            lxt_delays: List = None,
            theta: float = 22,
            sim = True,
            record = True
        ):

        """
        Performs a grid scan based on specified horizontal and vertical parameters.

        This method moves the sample in a grid pattern defined by horizontal and vertical
        parameters. It calculates movements based on trigonometry to achieve a specific
        scanning angle (22 degrees) and can optionally move DCCM and lxt delays if provided.

        Args:
        theta (float):
            Incline angle of the sample plane.

        h_params (Tuple[float, float, float]):
            Horizontal parameter x for scanning, consisting of the absolute start position,
            end position, and step size.
            Example: (0.0, 10.0, 1.0).

        v_params (Tuple[float, float, float]):
            Vertical parameters y and z for scanning (distance on sample between rows),
            consisting of the absolute start position, end position, and step size.
            Example: (0.0, 5.0, 0.5).

        z_at_0 (float):
            The z-coordinate at the starting point of the scan.

        dccm_energies (List, optional):
            A list of energies for DCCM (Differential Chromaticity Measurement)
            adjustments. If provided, its length must match the length of `h_pos`.

        lxt_delays (List, optional):
            A list of delays for LXT (likely relating to a specific experimental setup).
            Its length must match the length of `v_pos` if provided.

        """

        if sim:
            mot_x = sim_x
            mot_y = sim_y
            mot_z = sim_z
            lxt_ttc = sim_ttc
            dccm = sim_dccm
            print("Using simulated motors")

        else:
            mot_x = sam_x
            mot_y = sam_y
            mot_z = sam_z
            lxt_ttc = self.lxt_ttc
            dccm = self.dccm
            print("Using real motors")

        # absolute positions:
        h_positions = np.arange(h_params[0], h_params[1], h_params[2])
        v_positions = np.arange(v_params[0], v_params[1], v_params[2])

        print('\n')
        print("h_positions",h_positions)
        print("v_positions",v_positions)
        print("dccm_positions", dccm_energies)
        print("lxt_positions", lxt_delays)
        print('\n')

        theta = np.deg2rad(theta)  # convert to radian

        if dccm_energies is not None:
            err_msg = "length of DCCM array must match length of h_pos array"
            assert len(dccm_energies) == len(h_positions), err_msg
        if lxt_delays is not None:
            err_msg = "length of lxt_delays array must match length of v_pos array"
            assert len(lxt_delays) == len(v_positions), err_msg

        daq.begin(record=record,events=None)
        # Move X, Z and lxt position for every row
        for ii, v_pos in enumerate(v_positions):
            if lxt_delays is not None:
                lxt_ttc.move(lxt_delays[ii])
                print("lxt_delay", lxt_delays[ii])

            y_position = v_pos * np.sin(theta)
            z_position = v_pos * np.cos(theta)
            mot_y.move(y_position)
            mot_z.move(z_position)
            print(f"y_position: {y_position:0.04f}")
            print(f"z_position: {z_position:0.04f}")

            #  Move X and DCCM energy for each column
            for ii, x_pos in enumerate(h_positions):
                if dccm_energies is not None:
                    dccm.energy_with_vernier.move(dccm_energies[ii])
                    print("dccm_e", dccm_energies[ii])
                mot_x.move(x_pos)
                print(f"x_pos: {x_pos:0.04f}")
                seq.start()
                print("starting sequence")
                time.sleep(0.05)
                while seq.play_status.get() == 2: continue
                #yield from bps.trigger_and_read([seq, mot_x, mot_y, mot_z])  # bluesky way
            print('\n')
        daq.end_run()
        daq.disconnect()

        

    def full_scan_abs(self, h_params: Tuple[float, float, float], # (start, end, stepsize)
            v_params: Tuple[float, float, float], # (start, end, stepsize)
            z_at_IP: float,
            dccm_energies: List = None,
            lxt_delays: List = None,
            theta: float = 22,
            e_ref1 = 8.32,
            e_ref2 = 8.3895,
            sim = False,
            record = True):

        # prepare reference sequence
        self.prepare_sequence(nShotsPre=50,nShotsOn=0,nShotsPost=0)
        # move to below the edge
        dccm.energy_with_vernier.mvr(e_ref1)
        # first reference scan
        self.grid_scan_abs(h_params=h_params, v_params=v_params, z_at_IP=z_at_IP,
                record=record, sim=sim)

        # move to above the edge
        dccm.energy_with_vernier.mvr(e_ref2)
        # second reference scan
        self.grid_scan_abs(h_params=h_params, v_params=v_params, z_at_IP=z_at_IP,
                record=record, sim=sim)

        # prepare laser sequence
        self.prepare_sequence(nShotsPre=100,nShotsOn=1,nShotsPost=100)
        # laser scan
        self.grid_scan_abs(h_params=h_params, v_params=v_params, z_at_IP=z_at_IP,
                dccm_energies=dccm_energies,lxt_delays=lxt_delays, theta=theta,
                record=record, sim=sim)
    
    def grid_scan_rel(
            self,
            h_params: Tuple[float, float, float], # (start, end, stepsize)                                                                                         
            v_params: Tuple[float, float, float], # (start, end, stepsize)                                                                                         
            z_at_IP: float,
            dccm_energies: List = None,
            lxt_delays: List = None,
            theta: float = 22,
            sim = True,
            record = True
        ):

        """                                                                                                                                                        
        Performs a grid scan based on specified horizontal and vertical parameters relative to the current position.                                              \
                                                                                                                                                                   
                                                                                                                                                                   
        This method moves the sample in a grid pattern defined by horizontal and vertical                                                                          
        parameters. It calculates movements based on trigonometry to achieve a specific                                                                            
        scanning angle (22 degrees) and can optionally move DCCM and lxt delays if provided.                                                                       
                                                                                                                                                                   
        Args:                                                                                                                                                      
        theta (float):                                                                                                                                             
            Incline angle of the sample plane.                                                                                                                     
                                                                                                                                                                   
        h_params (Tuple[float, float, float]):                                                                                                                     
            Horizontal parameter x for scanning, consisting of the relative start position,                                                                        
            end position, and step size.                                                                                                                           
            Example: (0.0, 10.0, 1.0).                                                                                                                             
                                                                                                                                                                   
        v_params (Tuple[float, float, float]):                                                                                                                     
            Vertical parameters y and z for scanning (distance on sample between rows),                                                                            
            consisting of the relative start position, end position, and step size.                                                                                
            Example: (0.0, 5.0, 0.5).                                                                                                                              
                                                                                                                                                                   
        z_at_0 (float):                                                                                                                                            
            The z-coordinate at the starting point of the scan.                                                                                                    
                                                                                                                                                                   
        dccm_energies (List, optional):                                                                                                                            
            A list of energies for DCCM (Differential Chromaticity Measurement)                                                                                    
            adjustments. If provided, its length must match the length of `h_pos`.                                                                                 
                                                                                                                                                                   
        lxt_delays (List, optional):                                                                                                                               
            A list of delays for LXT (likely relating to a specific experimental setup).                                                                           
            Its length must match the length of `v_pos` if provided.                                                                                               
                                                                                                                                                                   
        """

        if sim:
            mot_x = sim_x
            mot_y = sim_y
            mot_z = sim_z
            lxt_ttc = sim_ttc
            dccm = sim_dccm
            print("Using simulated motors")

        else:
            mot_x = sam_x
            mot_y = sam_y
            mot_z = sam_z
            lxt_ttc = self.lxt_ttc
            dccm = self.dccm
            print("Using real motors")

        # absolute positions:                                                                                                                               
        h_positions = np.arange(h_params[0], h_params[1], h_params[2])
        v_positions = np.arange(v_params[0], v_params[1], v_params[2])

        print('\n')
        print("h_positions",h_positions)
        print("v_positions",v_positions)
        print("dccm_positions", dccm_energies)
        print("lxt_positions", lxt_delays)
        print('\n')

        theta = np.deg2rad(theta)  # convert to radian

        if dccm_energies is not None:
            err_msg = "length of DCCM array must match length of h_pos array"
            assert len(dccm_energies) == len(h_positions), err_msg
        if lxt_delays is not None:
            err_msg = "length of lxt_delays array must match length of v_pos array"
            assert len(lxt_delays) == len(v_positions), err_msg

        daq.begin(record=record,events=None)
        # Move X, Z and lxt position for every row                                                                                                          
        for ii, v_pos in enumerate(v_positions):
            if lxt_delays is not None:
                lxt_ttc.mvr(lxt_delays[ii])
                print("lxt_delay", lxt_delays[ii])

            y_position = v_pos * np.sin(theta)
            z_position = v_pos * np.cos(theta)
            mot_y.mvr(y_position)
            mot_z.mvr(z_position)
            print(f"y_position: {y_position:0.04f}")
            print(f"z_position: {z_position:0.04f}")

            #  Move X and DCCM energy for each column                                                                                                       
            for ii, x_pos in enumerate(h_positions):
                if dccm_energies is not None:
                    dccm.energy_with_vernier.mvr(dccm_energies[ii])
                    print("dccm_e", dccm_energies[ii])
                mot_x.mvr(x_pos)
                print(f"x_pos: {x_pos:0.04f}")
                seq.start()
                print("starting sequence")
                time.sleep(0.05)
                while seq.play_status.get() == 2: continue
                #yield from bps.trigger_and_read([seq, mot_x, mot_y, mot_z])  # bluesky way                                                                 
            print('\n')
        daq.end_run()
        daq.disconnect()


    def full_scan_rel(self, h_params: Tuple[float, float, float], # (start, end, stepsize)                                                                      
                      v_params: Tuple[float, float, float], # (relative start, end, stepsize)                                                            
                      z_at_IP: float,
                      dccm_energies: List = None,
                      lxt_delays: List = None,
                      theta: float = 22,
                      e_ref1 = 8.32,
                      e_ref2 = 8.3895,
                      sim = False,
                      record = True):

            # prepare reference sequence                                                                                                                        
            self.prepare_sequence(nShotsPre=50,nShotsOn=0,nShotsPost=0)
            # move to below the edge                                                                                                                            
            dccm.energy_with_vernier.mvr(e_ref1)
            # first reference scan                                                                                                                              
            self.grid_scan_rel(h_params=h_params, v_params=v_params, z_at_IP=z_at_IP,
                           record=record, sim=sim)

            # move to above the edge                                                                                                                            
            dccm.energy_with_vernier.mvr(e_ref2)
            # second reference scan                                                                                                                             
            self.grid_scan_rel(h_params=h_params, v_params=v_params, z_at_IP=z_at_IP,
                           record=record, sim=sim)

            # prepare laser sequence                                                                                                                            
            self.prepare_sequence(nShotsPre=100,nShotsOn=1,nShotsPost=100)
            # laser scan                                                                                                                                        
            self.grid_scan_rel(h_params=h_params, v_params=v_params, z_at_IP=z_at_IP,
                           dccm_energies=dccm_energies,lxt_delays=lxt_delays, theta=theta,
                           record=record, sim=sim)

class TargetVertical(PseudoPositioner):
    y_axis = Cpt(IMS, "XCS:GON:MMS:09", doc="y-axis gon motor", kind="normal", name='y_axis_gon')
    z_axis = Cpt(IMS,"XCS:GON:MMS:08", doc="z-axis gon motor", kind="normal", name='z_axis_gon')
    
    v_pos = Cpt(PseudoSingleInterface, doc='vertical position in the frame of the sample')

    def __init__(self,prefix="",name='vertical'):
        self.theta = 22
        super().__init__(prefix,name=name)
    @pseudo_position_argument
    def forward(self, pseudo_pos):
        """
        Virtual motor to move y and z axes in the frame of a sample at an angle.
        """
        
        theta = np.deg2rad(self.theta)  # convert to radians 
        
        pseudo_pos = self.PseudoPosition(*pseudo_pos)
        v_pos = pseudo_pos.v_pos
        y_position = v_pos * np.sin(theta)
        z_position = v_pos * np.cos(theta)
        return self.RealPosition(y_axis=y_position, z_axis=z_position)

    @real_position_argument
    def inverse(self, real_pos):
        """
        From the y and z axis motions, calculate the total vertical distance the sample traveled
        """
        theta = np.deg2rad(self.theta)  # convert to radians
        real_pos = self.RealPosition(*real_pos)
        v_pos = real_pos.y_axis/np.sin(theta)
        return self.PseudoPosition(v_pos=v_pos)
        

        
        
