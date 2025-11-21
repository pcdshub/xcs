import numpy as np
from hutch_python.utils import safe_load
from xcs.db import xcs_gon as gon, ladm
from ophyd import EpicsMotor
import json
import sys
import os
import socket
import logging
from ophyd import EpicsSignal
from ophyd.device import Device
from ophyd.device import Component as Cpt

from pcdsdevices.device_types import Newport, IMS
from pcdsdevices.epics_motor import SmarAct, EpicsMotorInterface
from pcdsdevices.interface import BaseInterface
from pcdsdevices.sim import FastMotor
#from xcs.db import RE, bpp, bps, seq, daq
from xcs.db import daq
import matplotlib.pyplot as plt
from xcs.beamline import show_cc, show_delay


class User():

    with safe_load('Interpulse delay virtual motor'): #used for Gopalan experiment user stage to convert mm to s        
        from pcdsdevices.device import Component as Cpt
        from pcdsdevices.pseudopos import DelayMotor, SyncAxis, delay_class_factory
        from xcs.db import xcs_delay
        DelayNewport = delay_class_factory(Newport)

        interpulse_delay_s = DelayNewport( 'XCS:USR:MMN:04', n_bounces=2, name='xcs_delay')
    

class cdiff_SmarAct(BaseInterface, Device):
    tab_component_names = True
    #mirr_x = Cpt(SmarAct, ':01:m1', kind='normal')                                                                                                                                                               
    #mirr_y = Cpt(SmarAct, ':01:m2', kind='normal')                                                                                                                                                               
    #mirr_dy = Cpt(SmarAct, ':01:m3', kind='normal')                                                                                                                                                              
    #mirr_dx = Cpt(SmarAct, ':01:m4', kind='normal')                                                                                                                                                              
    #mono_th = Cpt(SmarAct, ':01:m5', kind='normal')                                                                                                                                                              
    #pr_th = Cpt(SmarAct, ':01:m5', kind='normal')                                                                                                                                                                
    #pr_x = Cpt(SmarAct, ':01:m6', kind='normal')                                                                                                                                                                 
    #pr_y = Cpt(SmarAct, ':01:m7', kind='normal')                                                                                                                                                                 
    #las_rot = Cpt(SmarAct, ':01:m10', kind='normal')                                                                                                                                                             
    #lib_mirror_v = Cpt(SmarAct, ':01:m5', kind='normal')                                                                                                                                                         
    #pr_h = Cpt(SmarAct, ':01:m7', kind='normal')                                                                                                                                                                     #pr_th = Cpt(SmarAct, ':01:m9', kind='normal')                                                                                                                                                                
    #pr_v = Cpt(SmarAct, ':01:m8', kind='normal')                                                                                                                                                                 
    #mono1_th = Cpt(SmarAct, ':01:m6', kind='normal')                                                                                                                                                             
    #crl_y = Cpt(SmarAct, ':01:m1', kind='normal')                                                                                                                                                                
    #lib_mirror_h = Cpt(SmarAct, ':01:m2', kind='normal')                                                                                                                                                          
    sam_phi = Cpt(SmarAct, ':01:m4', kind='normal')
    sam_x = Cpt(SmarAct, ':01:m2', kind='normal')
    sam_z = Cpt(SmarAct, ':01:m3', kind='normal')
    sam_y = Cpt(SmarAct, ':01:m1', kind='normal')



class cdiff():#lib unit                                                                                                                                                                                            
    tab_component_names = True
    with safe_load('cdiff SmarAct'):
        lib = cdiff_SmarAct('XCS:MCS2', name='cdiff_smaract')
sam_phi = cdiff.lib.sam_phi
sam_y = cdiff.lib.sam_y
sam_x = cdiff.lib.sam_x
sam_z = cdiff.lib.sam_z
