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
from xcs.db import RE
from xcs.db import xcs_ccm as ccm
from xcs.delay_scan import delay_scan
from xcs.db import lxt_fast
from pcdsdevices.device_types import Newport, IMS
from elog import HutchELog

#from macros import *
import time

pickle.HIGHEST_PROTOCOL = 4
import pandas as pd

logger = logging.getLogger(__name__)

CAMS = [
        'xcs_gige_lj1'
        ]

CAM_PATH = '/cds/home/opr/xcsopr/experiments/xcsly5320/cam_data/'
SCAN_PATH = '/cds/home/opr/xcsopr/experiments/xcsly5320/scan_data/'

class CamTools:
    _camera = camviewer.xcs_gige_lj1
    _cam_type = 'gige'
    _path = CAM_PATH
    _images = []
    _timestamps = []
    _cb_uid = None
    _num_images = 10
    _state = 'idle'

    @property
    def camera(self):
        return self._camera

    @camera.setter
    def camera(self, camera):
        try:
            self._camera = getattr(camviewer, camera)
        except AttributeError as e:
            logger.warning(f'{camera} is not a valid camera: {e}')

    @property
    def height(self):
        if self.camera:
            return self.camera.image2.height.get()
        else:
            return None

    @property
    def width(self):
        if self.camera:
            return self.camera.image2.width.get()
        else:
            return None

    @property
    def file_path(self):
        return self._path

    @file_path.setter
    def file_path(self, path):
        # We'll have to validate or make path
        self._path = path

    @property
    def timestamps(self):
        return self._timestamps

    @property
    def images(self):
        return self._images

    @property
    def num_images(self):
        return self._num_images

    @num_images.setter
    def num_images(self, num):
        try:
            self._num_images = int(num)
        except:
            logger.warning('number of images must be castable as int')

    @staticmethod
    def camera_names():
        return CAMS

    def clear_data(self):
        self._images = []
        self._timestamps = []

    def collect(self, n_img):
        """General collection method.  If n_img specified, set
        property as well"""
        if not self.num_images:
            if n_img:
                self.num_images = n_img
            else:
                logger.warning('You need to specify number of images to collect')

        if self.images:
            logger.info('Leftover image data, clearing')
            self._images = []
            self._timestamps = []

        if not self.camera:
            logger.warning('You have not specified a camera')        
            return

        #if self.camera.cam.acquire.get() is not 1:
        #    logger.info('Camera has no rate, starting acquisition')
        #    self.camera.cam.acquire.put(1)

        cam_model = self.camera.cam.model.get()
        # TODO: Make dir with explicit cam model
        if 'opal' in cam_model:
            self._cam_type = 'opal'
        else:
            self._cam_type = 'gige'
        
        logger.info(f'Starting data collection for {self.camera.name}')
        #self._cb_uid = self.camera.image2.array_data.subscribe(self._data_cb)
        self._get_data()

    def _get_data(self):
        delay = 0.1
        while len(self.images) < self.num_images:
            img = self.camera.image2.array_data.get()
            ts = self.camera.image2.array_data.timestamp
            if len(self.images) == 0:
                self.images.append(np.reshape(img, (self.height, self.width)))
                self.timestamps.append(ts)
            if not np.array_equal(self.images[-1], img):
                print('getting image: ', len(self.images))
                self.images.append(np.reshape(img, (self.height, self.width)))
                self.timestamps.append(ts)
                print('delay ', time.time() - ts)
                time.sleep(delay)
            else:
                time.sleep(0.01)   
        logger.info('done collecting image data ')     

    def _data_cb(self, **kwargs):
        """Area detector cbs does not know thyself"""
        obj = kwargs.get('obj')
        arr = obj.value
        ts = obj.timestamp
        self.images.append(np.reshape(arr, (self.height, self.width)))
        self.timestamps.append(ts)
        logger.info('received image: ', len(self.images), time.time() - ts)
        if len(self.images) >= self.num_images:
            logger.info('We have collected all our images, stopping collection')
            self.camera.image2.array_data.unsubscribe(self._cb_uid)

    def plot(self):
        """Let people look at collected images"""
        if not self.images:
            info.warning('You do not have any images collected')

        num_images = len(self.images)
        img_sum = self.images[0]
        if num_images is 1:
            plt.imshow(img_sum)
        else:
            for img in self.images[1:]:
                img_sum += img
            plt.imshow(img_sum / num_images)

    def save(self):
        file_name = f'{self.camera.name}-{int(time.time())}.h5'
        location = ''.join([self._path, file_name])
        hf = h5py.File(location, 'w')
        hf.create_dataset('image_data', data=self.images)
        hf.create_dataset('timestamps', data=self.timestamps)
        hf.close()
        logger.info(f'wrote all image data to {location}')
        return location


class ImagerHdf5():
    def __init__(self, imager=None):
        try:
            self.imagerh5 = imager.hdf51
            self.imager = imager.cam
        except:
            self.imagerh5 = None
            self.imager = None
            
    def setImager(self, imager):
        self.imagerh5 = imager.hdf51
        self.imager = imager.cam
        
    def stop(self):
        self.imagerh5.enable.set(0)

    def status(self):
        print('Enabled',self.imagerh5.enable.get())
        print('File path',self.imagerh5.file_path.get())
        print('File name',self.imagerh5.file_name.get())
        print('File template (should be %s%s_%d.h5)',self.imagerh5.file_template.get())

        print('File number',self.imagerh5.file_number.get())
        print('Frame to capture per file',self.imagerh5.num_capture.get())
        print('autoincrement ',self.imagerh5.auto_increment.get())
        print('file_write_mode ',self.imagerh5.file_write_mode.get())
        #IM1L0:XTES:CAM:HDF51:Capture_RBV 0: done, 1: capturing
        print('captureStatus ',self.imagerh5.capture.get())

    def prepare(self, baseName=None, pathName=None, nImages=None, nSec=None):
        if self.imagerh5.enable.get() != 'Enabled':
            self.imagerh5.enable.put(1)
        iocdir=self.imager.prefix.split(':')[0].lower()
        if pathName is not None:
            self.imagerh5.file_path.set(pathName)
        elif len(self.imagerh5.file_path.get())==0:
            #this is a terrible hack.
            iocdir=self.imager.prefix.replace(':','-').lower()[:-1]
            camtype='gige'
            self.imagerh5.file_path.put('/reg/d/iocData/ioc-%s/'%(iocdir))
            if 'rix' in iocdir:
                self.imagerh5.file_path.put('/reg/d/iocData/ioc-cam-%s/'%(iocdir))

        if baseName is not None:
            self.imagerh5.file_name.put(baseName)
        else:
            expname = check_output('get_curr_exp').decode('utf-8').replace('\n','')
            try:
                lastRunResponse = check_output('get_lastRun').decode('utf-8').replace('\n','')
                if lastRunResponse == 'no runs yet': 
                    runnr=0
                else:
                    runnr = int(check_output('get_lastRun').decode('utf-8').replace('\n',''))
            except:
                runnr = 0
            self.imagerh5.file_name.put('%s_%s_Run%03d'%(iocdir,expname, runnr+1))

        self.imagerh5.file_template.put('%s%s_%d.h5')
        #check that file to be written does not exist
        already_present = True
        while (already_present):
            fnum = self.imagerh5.file_number.get()
            fname = self.imagerh5.file_path.get() + self.imagerh5.file_name.get() + \
                    '_%d'%fnum + '.h5'
            if os.path.isfile(fname):
                print('File %s already exists'%fname)
                self.imagerh5.file_number.put(1 + fnum)
                time.sleep(0.2)
            else:
                already_present = False

        self.imagerh5.auto_increment.put(1)
        self.imagerh5.file_write_mode.put(2)
        if nImages is not None:
            self.imagerh5.num_capture.put(nImages)
        if nSec is not None:
            if self.imager.acquire.get() > 0:
                rate = self.imager.array_rate.get()
                self.imagerh5.num_capture.put(nSec*rate)
            else:
                print('Imager is not acquiring, cannot use rate to determine number of recorded frames')

    def write(self, nImages=None):
        if nImages is not None:
            self.imagerh5.num_capture.put(nImages)
        if self.imager.acquire.get() == 0:
            self.imager.acquire.put(1)
        self.imagerh5.capture.put(1)

    def write_wait(self, nImages=None):
        while (self.imagerh5.num_capture.get() > 
               self.imagerh5.num_captured.get()):
            time.sleep(0.25)

    def write_stop(self):
        self.imagerh5.capture.put(0)


class User():
    _cam_tools = CamTools()
    def __init__(self):
        with safe_load('SmarAct'):
            self.las1 = SmarActTipTilt(prefix='XCS:MCS2:01', tip_pv=':m1', tilt_pv=':m2', name='las1')
            self.las2 = SmarActTipTilt(prefix='XCS:MCS2:01', tip_pv=':m4', tilt_pv=':m5', name= 'las2')
            self.las3 = SmarActTipTilt(prefix='XCS:MCS2:01', tip_pv=':m7', tilt_pv=':m8', name = 'las3')
        with safe_load('elog'):
            kwargs = dict()
            self.elog = HutchELog.from_conf('XCS', **kwargs)

        with safe_load('cameras'):
            self. = ImagerHdf5(camviewer.xcs_gige_lj1)
#            self.intermediate_fieldh5 = ImagerHdf5(getattr(camviewer,'cam-crix-gige-03'))

        #with safe_load('lw9319_motors'):
        #    self.bf_det_y = IMS('XCS:USR:MMS:33', name='bf_det_y')
        #    self.gon_mid_Rz = IMS('XCS:USR:MMS:35', name='gon_mid_Rz')
        #    self.gon_mid_x = IMS('XCS:USR:MMS:48', name='gon_mid_x')
        #    self.gon_mid_z = IMS('XCS:USR:MMS:45', name='gon_mid_z')
        #    self.gon_mid_Rx = IMS('XCS:USR:MMS:44', name='gon_mid_Rx')
        #    self.crl_df_Rx = IMS('XCS:USR:MMS:39', name='crl_df_Rx')
        #    self.crl_df_y = IMS('XCS:USR:MMS:40', name='crl_df_y')
        #    self.crl_df_x = IMS('XCS:USR:MMS:47', name='crl_df_x')
        #    self.crl_bf_Rx = IMS('XCS:USR:MMS:37', name='crl_bf_Rx')
        #    self.crl_bf_x = IMS('XCS:USR:MMS:38', name='crl_bf_x')
        #    self.bf_det_x = IMS('XCS:USR:MMS:34', name='bf_det_x')
        #    self.gon_mid_y = IMS('XCS:USR:MMS:03', name='gon_mid_y')
        #    self.crl_bf_y = IMS('XCS:USR:MMS:05', name='crl_bf_y')
        #    self.gon_mid_Ry = Newport('XCS:USR:MMN:03', name='gon_mid_Ry')
        #    self.nf_x = Newport('XCS:USR:MMN:07', name='nf_x')
        #    self.crl_df_Ry = Newport('XCS:USR:MMN:05', name='crl_df_Ry')
        #    self.crl_bf_z = Newport('XCS:USR:MMN:06',name = 'crl_bf_z')
        #    self.crl_df_z = Newport('XCS:USR:MMN:05',name = 'crl_df_z')
        #    self.crl_bf_Ry = Newport('XCS:USR:MMN:04', name='crl_bf_Ry')
        #    self.bf_det_focus = Newport('XCS:LADM:MMN:01',name = 'bf_det_focus')
        #    self.df_det_focus = Newport('XCS:LADM:MMN:02',name = 'df_det_focus')
        #    #self.sam_x = MMC('',name = 'sam_x')
        #    #self.sam_y = MMC('',name = 'sam_y') 

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


    def list2scan(self, m1, p1, m2, p3, nEvents, record=None, use_l3t=False, post=False):
        self.cleanup_RE()
        currPos1 = m1.wm()
        currPos2 = m2.wm()
        daq.configure(nEvents, record=record, controls=[m1,m2], use_l3t=use_l3t)
        try:
            RE(list_grid_scan([daq], m1,p1,m2,p3))
        except Exception:
            logger.debug('RE Exit', exc_info=True)
        finally:
            self.cleanup_RE()
        m1.mv(currPos1)
        m2.mv(currPos2)

        if post:
            run = get_run()
            message = 'grid scan with {name1} from {min1:.3f} to {max1:.3f} in {num1} steps, and {name2} from {min2:.3f} to {max2:.3f} in {num2} steps'.format(name1=m1.name,
                        min1=p1[0],max1=p1[-1],
                        num1=p1.size, name2=m2.name, 
                        min2=p2[0],max2=p2[-1],num2=p2.size)
            self.elog.post(message,run=int(run))





    def loop_newport_dscan(self, m1, start1, stop1, m2, start2, stop2, loop_steps, m3_newport, start3, stop3, run_steps, nEvents, record=None, use_l3t=False, post=False):
        # m1 is the slow motor, m2 is the fast motor
        self.cleanup_RE()
        currPos1 = m1.wm()
        currPos2 = m2.wm()
        currPos3 = m3_newport.wm()

        m1_pos = np.linspace(start1+currPos1, stop1+currPos1, loop_steps)
        m2_pos = np.linspace(start2+currPos2, stop2+currPos2, loop_steps)
        
        for m1pos, m2pos in zip(m1_pos, m2_pos):
            # move to next row and wait until motor gets there
            m1.mv(m1pos, wait=True)
            m2.mv(m2pos, wait=True)
            
            self.newport_dscan(m3_newport, start3, stop3, run_steps, nEvents, record=record, use_l3t=use_l3t, post=post)
            
        # move back to original positions
        m1.mv(currPos1)
        m2.mv(currPos2)
        m3_newport.mv(currPos3-0.1, wait=True)
        m3_newport.mv(currPos3, wait=True)

        if post:
            run = get_run()
            message = f'runs {int(run)-loop_steps+1} to {run} are a quasi-2D scan of {m1.name}, {m2.name} and {m3_newport.name}'
            self.elog.post(message,run=int(run))

    def loop_dscan(self, m1, start1, stop1, loop_steps, m2, start2, stop2, run_steps, nEvents, record=None, use_l3t=False, post=False):
        # m1 is the slow motor (assumed to be Newport), m2 is the fast motor
        self.cleanup_RE()
        currPos1 = m1.wm()
        currPos2 = m2.wm()

        m1_pos = np.linspace(start1+currPos1, stop1+currPos1, loop_steps)
        
        # take care of backlash
        m1.mv(currPos1-0.1, wait=True)
        

        for m1pos in m1_pos:
            # move to next row and wait until motor gets there
            m1.mv(m1pos, wait=True)
            
            self.dscan(m2, start2, stop2, run_steps, nEvents, record=record, use_l3t=use_l3t, post=post)
            #if post:
            #    # get run number
            #    run = get_run()
            #    message = '{name1}={pos:.3f}, and scan {name2} from {min2:.3f} to {max2:.3f} in {num2} steps'.format(name1=m1.name,pos=m1pos,name2=m2.name,
            #            min2=np.min(m2_pos),max2=np.max(m2_pos),
            #            num2=np.size(m2_pos))

            #    self.elog.post(message,run=int(run))
            m2.mv(currPos2,wait=True)
      
        # move back to original positions
        m1.mv(currPos1-0.1,wait=True)
        m1.mv(currPos1)
        m2.mv(currPos2)
    

    
    def loop_d2scan(self, m1, start1, stop1, loop_steps, m2, start2, stop2, m3, start3, stop3, run_steps, nEvents, record=None, use_l3t=False, post=False):
        # m1 is the slow motor, m2 is the fast motor
        self.cleanup_RE()
        currPos1 = m1.wm()
        currPos2 = m2.wm()
        currPos3 = m3.wm()

        m1_pos = np.linspace(start1+currPos1, stop1+currPos1, loop_steps)
        
        # take care of backlash
        m1.mv(currPos1-0.1, wait=True)
        

        for m1pos in m1_pos:
            # move to next row and wait until motor gets there
            m1.mv(m1pos, wait=True)
            
            self.d2scan(m2, start2, stop2, m3, start3, stop3, run_steps, nEvents, record=record, use_l3t=use_l3t, post=post)
            #if post:
            #    # get run number
            #    run = get_run()
            #    message = '{name1}={pos:.3f}, and scan {name2} from {min2:.3f} to {max2:.3f} in {num2} steps'.format(name1=m1.name,pos=m1pos,name2=m2.name,
            #            min2=np.min(m2_pos),max2=np.max(m2_pos),
            #            num2=np.size(m2_pos))

            #    self.elog.post(message,run=int(run))
            m2.mv(currPos2,wait=True)
            m3.mv(currPos3,wait=True)
      
        # move back to original positions
        m1.mv(currPos1-0.1,wait=True)
        m1.mv(currPos1)
        m2.mv(currPos2)
        m3.mv(currPos3)
    

    def line_scan(self, m1, start1, stop1, steps1, m2, start2, stop2, steps2, nEvents, record=None, use_l3t=False, post=False):
        # m1 is the slow motor, m2 is the fast motor
        self.cleanup_RE()
        currPos1 = m1.wm()
        currPos2 = m2.wm()
    
        if type(steps1)==int:
            m1_pos = np.linspace(start1, stop1, steps1)
        elif type(steps1)==float:
            m1_pos = np.arange(start1, stop1+steps1, steps1)
        else:
            return
        if type(steps2)==int:
            m2_pos = np.linspace(start2, stop2, steps2)
        elif type(steps2)==float:
            m2_pos = np.arange(start2, stop2+steps2, steps2)
        else:
            return

        for m1pos in m1_pos:
            # move to next row and wait until motor gets there
            m1.mv(m1pos, wait=True)
            
            daq.configure(nEvents, record=record, controls=[m2], use_l3t=use_l3t)
            try:
                RE(list_scan([daq],m2, m2_pos))
            except Exception:
                logger.debug('RE Exit', exc_info=True)
            finally:
                self.cleanup_RE()
            
            if post:
                # get run number
                run = get_run()
                message = '{name1}={pos:.3f}, and scan {name2} from {min2:.3f} to {max2:.3f} in {num2} steps'.format(name1=m1.name,pos=m1pos,name2=m2.name,
                        min2=np.min(m2_pos),max2=np.max(m2_pos),
                        num2=np.size(m2_pos))

                self.elog.post(message,run=int(run))
        
        m1.mv(currPos1)
        m2.mv(currPos2)
    
    def dline_scan(self, m1, start1, stop1, steps1, m2, start2, stop2, steps2, nEvents, record=None, use_l3t=False, post=False):

        currPos1 = m1.wm()
        currPos2 = m2.wm()
        self.line_scan(m1,start1+currPos1, stop1+currPos1, steps1, m2, start2+currPos2, stop2+currPos2, steps2, nEvents, record=record, use_l3t=use_l3t, post=post) 


    def list3scan(self, m1, p1, m2, p2, m3, p3, nEvents, record=None, use_l3t=False, post=False):
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

    def dscan(self, motor, start, end, nsteps, nEvents, record=None, use_l3t=False, post=False):
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
        
        if post:
            run = get_run()
            message = 'scan {name} from {min1:.3f} to {max1:.3f} in {num1} steps'.format(name=motor.name,
                        min1=start+currPos,max1=end+currPos,
                        num1=nsteps)
            self.elog.post(message,run=int(run))

    def newport_dscan(self, motor, start, end, nsteps, nEvents, record=None, use_l3t=False, post=False):
        self.cleanup_RE()
        daq.configure(nEvents, record=record, controls=[motor], use_l3t=use_l3t)
        currPos = motor.wm()
        
        # remove backlash for small scans
        motor.mvr(-.1, wait=True)

        try:
            RE(scan([daq], motor, currPos+start, currPos+end, nsteps))
        except Exception:
            logger.debug('RE Exit', exc_info=True)
        finally:
            self.cleanup_RE()

        # move back to starting point and remove backlash
        motor.mv(currPos, wait=True)
        motor.mvr(-0.1, wait=True)
        motor.mv(currPos)
        
        if post:
            run = get_run()
            message = 'scan {name} from {min1:.3f} to {max1:.3f} in {num1} steps'.format(name=motor.name,
                        min1=start+currPos,max1=end+currPos,
                        num1=nsteps)
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
        daq.configure(events=None, duration=None, record=record,
                      use_l3t=use_l3t, controls=[lxt_fast])
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


    def empty_delay_scan(self, start, end, sweep_time, record=None,
                         use_l3t=False, duration=None, post=False):
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

    @property
    def cam_tools(self):
        return self._cam_tools

    def scanner(self, motor, start, stop, steps, cam, images=10, post=False):
        """General scanner for now because we want to take images"""

        currPos = motor.wm()
        steps = np.linspace(start, stop, steps)
        times = []
        image_files = []
        self.cam_tools.camera = cam
        df = pd.DataFrame()
        for step in steps:
            motor.mv(step, wait=True)
            logger.info(f'Stepper reached {step}, collecting data')
            times.append(time.time())
            self.cam_tools.num_images = images
            self.cam_tools.collect(images)
            f = self.cam_tools.save()
            image_files.append(f)
            df = df.append(pd.DataFrame([step], columns=[motor.name]), ignore_index=True) 
            #df = df.append(pd.DataFrame([caget_many(EPICSARCH)], columns=EPICSARCH), ignore_index=True)
        df = df.assign(times=times)
        df = df.assign(image_files=image_files)
        file_name = f'{motor.name}-{int(time.time())}.h5'
        location = SCAN_PATH + file_name
        df.to_hdf(location, key='metadata')
        logger.info(f'wrote all data to {location}')

        motor.mv(currPos)

        if post:
            run = get_run()
            message = 'scan {name} from {min1} to {max1} in {num1} steps, recording images with {cam}'.format(name=motor.name,
                        min1=start,max1=stop,
                        num1=steps.size, cam=cam)
            message += f"\n\nwrote all data to {location}"
            self.elog.post(message)

    

