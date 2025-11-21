import numpy as np
from hutch_python.utils import safe_load
from xcs.db import xcs_gon as gon, ladm
from ophyd import EpicsMotor
import scipy.optimize as optimize
import json
import sys
import time
from datetime import datetime
import os
import socket
import logging
from ophyd import EpicsSignal

from pcdsdevices.device_types import Newport, IMS
from pcdsdevices.sim import FastMotor
#from xcs.db import RE, bpp, bps, seq, daq, pp
from xcs.db import daq, pp, seq
import matplotlib.pyplot as plt
from scipy.stats import qmc
from xcs.beamline import show_cc, show_delay

from bluesky.plans import list_scan, scan
from databroker import Broker

from ophyd.device import Device
from ophyd.status import StatusBase, SubscriptionStatus
from threading import RLock
from ophyd.status import DeviceStatus
from ophyd.signal import EpicsSignalRO, Signal
from ophyd.device import Component as Cpt
from pcdsdevices.signal import AvgSignal
from hxrsnd.sndsystem import SplitAndDelay
from hxrsnd.sndmotor import SndEpicsMotor
from hxrsnd.aerotech import AeroBase

from xopt import Xopt, Evaluator
import torch
import gpytorch
import botorch
from xopt import VOCS
from xopt.generators.bayesian import ExpectedImprovementGenerator, UpperConfidenceBoundGenerator
from xopt.resources.test_functions.tnk import evaluate_TNK, tnk_vocs
import pandas as pd


class User():
    with safe_load('Dummy'):
        gon_2th=gon.rot_2theta
        print('Import dummy')
    
    def __init__(self):
        ipm4 = EpicsSignalRO('XCS:SB1:BMMON:SUM')
        ipm5 = EpicsSignalRO('XCS:SB2:BMMON:SUM')    

    def takeRun(self, nEvents=None, duration=None, record=True, use_l3t=False):
        daq.configure(events=120, record=record, use_l3t=use_l3t)
        daq.begin(events=nEvents, duration=duration)
        daq.wait()
        daq.end_run()
    def move_gontth(self,tth=5,z_offset=152.4,det_position=690):
        """ move the gon 2th with z_offset """
        target_tth = np.rad2deg(np.arctan(((det_position-z_offset)*np.tan(np.deg2rad(tth)))/det_position))
        print(target_tth)
        user_input = input("Do you want move ?(y/n): ")
        if user_input.lower() in["yes","y"]:
            self.gon_2th.umv(target_tth)
        else :
            return

    def move_ladm_out(self):
        ladm.z.umv(-150);
        ladm.x1.umv(778);
        return
    def move_ladm_in(self):
        ladm.z.umv(-200)
        ladm.x1.umv(678.012)
        return

    def dumbSnake_delay_scan(self, xStart, xEnd, yDelta,thStart, thDelta, nRoundTrips,sweepTime):
        """ 
        simple rastering for running at 120Hz with shutter open/close before
        and after motion stop.
         
        Need some testing how to deal with intermittent motion errors.
        """
        self.sam_x.umv(xStart)
        self.t34th.umv(thStart)
        #sweeptime = abs(xStart-xEnd)/7
        daq.connect()
        daq.begin(record = True, events = -1)
        time.sleep(2)
        print('Reached horizontal start position')
        # looping through n round trips
        for i in range(nRoundTrips):
            
            print('starting round trip %d' % (i+1))
            self.sam_x.mv(xEnd)
            time.sleep(0.2)
            pp.open()
            seq.start()
            time.sleep(sweepTime)
            seq.stop()
            pp.close()
            self.sam_x.wait()
            self.sam_y.umvr(yDelta)
            self.t34th.umvr(thDelta)
            time.sleep(0.5)#orignal was 1
            self.sam_x.mv(xStart)
            time.sleep(0.2)
            pp.open()
            seq.start()
            time.sleep(sweepTime)
            seq.stop()
            pp.close()
            self.sam_x.wait()
            self.sam_y.umvr(yDelta)
            print('ypos',self.sam_y.wm())
            time.sleep(0.5)#original was 1
            #except:
                #print('round trip %d didn not end happily' % i)
        daq.end_run()
        daq.disconnect()

    def dumbSnake(self, xStart, xEnd, yDelta, nRoundTrips,sweepTime):
        """ 
        simple rastering for running at 120Hz with shutter open/close before
        and after motion stop.
         
        Need some testing how to deal with intermittent motion errors.
        """
        self.sam_x.umv(xStart)
        #sweeptime = abs(xStart-xEnd)/7
        daq.connect()
        daq.begin(record = True, events = -1)
        time.sleep(2)
        print('Reached horizontal start position')
        # looping through n round trips
        for i in range(nRoundTrips):
            
            print('starting round trip %d' % (i+1))
            self.sam_x.mv(xEnd)
            time.sleep(0.2)
            pp.open()
            seq.start()
            time.sleep(sweepTime)
            seq.stop()
            pp.close()
            self.sam_x.wait()
            self.sam_y.umvr(yDelta)
            time.sleep(0.5)#orignal was 1
            self.sam_x.mv(xStart)
            time.sleep(0.2)
            pp.open()
            seq.start()
            time.sleep(sweepTime)
            seq.stop()
            pp.close()
            self.sam_x.wait()
            self.sam_y.umvr(yDelta)
            print('ypos',self.sam_y.wm())
            time.sleep(0.5)#original was 1
            #except:
                #print('round trip %d didn not end happily' % i)
        daq.end_run()
        daq.disconnect()

    def dumbSnake_forever(self, xStart, xEnd, yDelta, nRoundTrips,sweepTime):
        """ 
        simple rastering for running at 120Hz with shutter open/close before
        and after motion stop.
         
        Need some testing how to deal with intermittent motion errors.
        """
        self.sam_x.umv(xStart)
        #sweeptime = abs(xStart-xEnd)/7
        daq.connect()
        daq.begin(record = True, events = -1)
        time.sleep(2)
        print('Reached horizontal start position')
        # looping through n round trips
        for i in range(nRoundTrips):
            
            print('starting round trip %d' % (i+1))
            self.sam_x.mv(xEnd)
            time.sleep(0.2)
            pp.open()
            seq.start()
            time.sleep(sweepTime)
            seq.stop()
            pp.close()
            self.sam_x.wait()
            self.sam_y.umvr(yDelta)
            time.sleep(0.5)#orignal was 1
            self.sam_x.mv(xStart)
            time.sleep(0.2)
            pp.open()
            seq.start()
            time.sleep(sweepTime)
            seq.stop()
            pp.close()
            self.sam_x.wait()
            self.sam_y.umvr(yDelta)
            print('ypos',self.sam_y.wm())
            time.sleep(0.5)#original was 1
            #except:
                #print('round trip %d didn not end happily' % i)
        daq.end_run()
#        daq.disconnect()

class Util:

    @staticmethod
    def fit_gaussian(x, x0, w):
        """
        Method for fitting to a Gaussian function. This method is a parameter to Scipy's optimize.curve_fit routine.
        :param x: array_like
            Copied from Scipy docs: "The independent variable where the data is measured. Should usually be an
            M-length sequence or an (k,M)-shaped array for functions with k predictors, but can actually be any
            object." Units are meters.
        :param x0: float
            Initial guess for beam center (m).
        :param w: float
            Initial guess for gaussian sigma (m).
        :return: array_like with same shape as x
            Function evaluated at all points in x.
        """
        # just return an array evaluating the Gaussian function based on input parameters.
        if w == 0:
            return np.zeros_like(x)
        else:
            return np.exp(-((x - x0) ** 2 / (2 * w ** 2)))

    @staticmethod
    def gaussian_stats(x_data, y_data, thresh=0.1,sigma=None):

        # normalize input (and subtract any offset)
        y_norm = Util.normalize_trace(y_data)
        # threshold input
        y_data_thresh = Util.threshold_array(y_norm, thresh)

        # calculate centroid
        cx = np.sum(y_data_thresh * x_data) / np.sum(y_data_thresh)

        # calculate second moment
        sx = np.sqrt(np.sum(y_data_thresh * (x_data - cx) ** 2) / np.sum(y_data_thresh))
        fwx_guess = sx * 2.355

        guess = [cx, sx]

        try:
            mask = y_data_thresh > 0
            px, pcovx = optimize.curve_fit(Util.fit_gaussian, x_data[mask], y_norm[mask],p0=guess,sigma=sigma)
            sx = px[1]
        except:
            print('Fit failed. Using second moment for width.')

        return cx, sx

    @staticmethod
    def normalize_trace(y_data):

        norm_data = (y_data - np.min(y_data))/(np.max(y_data) - np.min(y_data))

        return norm_data

    @staticmethod
    def threshold_array(array_in, frac):
        """Method for thresholding an array, useful for calculating center of mass
        :param array_in: array-like
            can be any shape array
        :param frac: float
            threshold fraction of image maximum
        :return array_out: array-like
            thresholded array, same shape as array_in
        """

        # make sure the image is not complex
        array_out = np.abs(array_in)

        # subtract minimum/background
        array_out -= np.min(array_out)

        # get thresholding level
        thresh = np.max(array_out) * frac
        # subtract threshold level
        array_out = array_out - thresh
        # set anything below threshold (now 0) to zero
        array_out[array_out < 0] = 0

        return array_out


