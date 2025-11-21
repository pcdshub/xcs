import time
import os

from hutch_python.utils import safe_load
from xpp.db import xpp_attenuator as att
from pcdsdevices.device_types import Newport, IMS

class User():
    def __init__(self):


    def move_zyla(self):
        att(1e-6)
        self.gon_sy.mv_zyla()
        self.sam_x.umv_zyla() 
        att(0.1)
        self.show_cc()
        print ('zyla')

    def move_sample(self):
        att(1e-6)
        self.gon_sy.mv_sample()
        self.sam_x.umv_sample() 
        att(0.1)
        print ('sample att 0.1')
