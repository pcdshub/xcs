from subprocess import check_output

import json
import sys
import time

import numpy as np
from ophyd import EpicsSignalRO
from ophyd import EpicsSignal
from bluesky import RunEngine
from bluesky.plans import scan
from ophyd import Component as Cpt
from ophyd import Device
from pcdsdevices.interface import BaseInterface
from xcs.db import daq
from xcs.db import camviewer
from xcs.db import RE
#move this to beamline with the most typical detectors.
from pcdsdaq.ami import AmiDet

class PPM_Record():
    def __init__(self, pvname='IM3L0:PPM:SPM:VOLT_BUFFER_RBV',time=1, 
                   filename=None):
        self.collection_time = time
        self.arr = []
        self.pvname = pvname
        self.sig = EpicsSignalRO(pvname)
        try:
            self.sig.wait_for_connection(timeout=3.0)
        except TimeoutError:
            print(f'Could not connect to data PV {pvname}, timed out.')
            print('Either on wrong subnet or the ioc is off.')
        if filename is not None:
            self.filename = filename
        else:
            self.setFilename()

    def cb10(self, value, **kwargs):
        #print('value ',value)
        # Downsample to 10Hz from 1000Hz
        for i in range(10):
            self.arr.append(np.mean(value[100*i:100*(i+1)]))
        #print('{} values collected'.format(len(self.arr)))


    def cb100(self, value, **kwargs):
        # Downsample to 100Hz from 1000Hz
        for i in range(100):
            self.arr.append(np.mean(value[10*i:10*(i+1)]))

    def cb(self, value, **kwargs):
        self.arr.append(value)

    def setCollectionTime(self, ctime=None):
        self.collection_time = ctime

    def collectData(self, rate=10):
        if rate==100:
            cbid = self.sig.subscribe(self.cb100)
        elif rate==10:
            cbid = self.sig.subscribe(self.cb10)
        else:
            cbid = self.sig.subscribe(self.cb)
        time.sleep(self.collection_time)
        self.sig.unsubscribe(cbid)

    def setFilename(self, basename=None, useTime=False):
        if basename is None:
            basename = self.pvname.split(':')[0]+'_powermeter_data'
        if useTime:
            self.filename = basename+'_{}'.format(int(time.time()))
        else:
            self.filename = basename
        
    def writeFile(self):
        #print('saving to {}'.format(self.filename))
        with open(self.filename, 'w') as fd:
            for value in self.arr:
                print(value, file=fd)
        #if len(self.arr) == 0:
        #    print('Warning: no data points collected! File is empty!')
        self.arr = []


class ImagerStats3():

    def __init__(self, imager_name=None):
        pass

    def setImager(self, imager_name):
        pass


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
            self.imagerh5.enable.set(1)
        if pathName is not None:
            self.imagerh5.file_path.set(pathName)
        elif len(self.imagerh5.file_path.get())==0:
            #this is a terrible hack.
            iocdir=self.imager.prefix.split(':')[0].lower()
            camtype='opal'
            if (self.imager.prefix.find('PPM')>0): camtype='gige'
            self.imagerh5.file_path.set('/reg/d/iocData/ioc-%s-%s/images/'%(iocdir, camtype))
        if baseName is not None:
            self.imagerh5.file_name.set(baseName)
        else:
            expname = check_output('get_curr_exp').decode('utf-8').replace('\n','')
            try:
                runnr = int(check_output('get_lastRun').decode('utf-8').replace('\n',''))
            except:
                runnr = 0
            self.imagerh5.file_name.set('%s_Run%03d'%(expname, runnr+1))

        self.imagerh5.file_template.set('%s%s_%d.h5')
        self.imagerh5.auto_increment.set(1)
        self.imagerh5.file_write_mode.set(2)
        if nImages is not None:
            self.imagerh5.num_capture.set(nImages)
        if nSec is not None:
            if self.imager.acquire.get() > 0:
                rate = self.imager.array_rate.get()
                self.imagerh5.num_capture.set(nSec*rate)
            else:
                print('Imager is not acquiring, cannot use rate to determine number of recorded frames')

    def write(self, nImages=None):
        if nImages is not None:
            self.imagerh5.num_capture.set(nImages)
        if self.imager.acquire.get() == 0:
            self.imager.acquire.set(1)
        self.imagerh5.capture.set(1)

    def write_wait(self, nImages=None):
        while (self.imagerh5.num_capture.get() > 
               self.imagerh5.num_captured.get()):
            time.sleep(0.25)

class ImagerStats():
    def __init__(self, imager=None):
        try:
            self.imgstat = imager.stats1
        except:
            self.imgstat = None
            
    def setImager(self, imager):
        self.imgstat = imager.stats1

    def stop(self):
        self.imgstat.enable.set(0)

    def setThreshold(self, nSigma=1):
        self.imgstat.enable.set(1)
        computeStat = self.imgstat.compute_statistics.get()
        self.imgstat.compute_statistics.set(1)
        mean = self.imgstat.mean_value.get()
        sigma = self.imgstat.sigma.get()
        self.imgstat.centroid_threshold.set(mean+sigma*nSigma)
        self.imgstat.compute_statistics.set(computeStat)

    def prepare(self, threshold=None):
        self.imager.acquire.set(1)
        if self.imgstat.enable.get() != 'Enabled':
            self.imgstat.enable.set(1)
        if threshold is not None:
            if self.imgstat.compute_centroid.get() != 'Yes':
                self.imgstat.compute_centroid.set(1)
            self.imgstat.centroid_threshold.set(threshold)
        self.imgstat.compute_profiles.set(1)
        self.imgstat.compute_centroid.set(1)

    def status(self):
        print('enabled:', self.imgstat.enable.get())
        if self.imgstat.enable.get() == 'Enabled':
            if self.imgstat.compute_statistics.get() == 'Yes':
                #IM1L0:XTES:CAM:Stats1:MeanValue_RBV
                #IM1L0:XTES:CAM:Stats1:SigmaValue_RBV
                print('Mean', self.imgstat.mean_value.get())
                print('Sigma', self.imgstat.sigma.get())
            if self.imgstat.compute_centroid.get() == 'Yes':
                print('Threshold', self.imgstat.centroid_threshold.get())
                #IM1L0:XTES:CAM:Stats1:CentroidX_RBV
                #IM1L0:XTES:CAM:Stats1:CentroidY_RBV
                #IM1L0:XTES:CAM:Stats1:SigmaX_RBV
                #IM1L0:XTES:CAM:Stats1:SigmaY_RBV
                print('X,y', self.imgstat.centroid.get())
                print('sigma x', self.imgstat.sigma_x.get())
                print('sigma y', self.imgstat.sigma_y.get())
            if self.imgstat.compute_profiles.get() == 'Yes':
                #IM1L0:XTES:CAM:Stats1:CursorX
                #IM1L0:XTES:CAM:Stats1:CursorY
                print('profile cursor values: ',self.imgstat.cursor.get())
                #IM1L0:XTES:CAM:Stats1:ProfileAverageX_RBV
                #IM1L0:XTES:CAM:Stats1:ProfileAverageY_RBV
                #IM1L0:XTES:CAM:Stats1:ProfileThresholdX_RBV
                #IM1L0:XTES:CAM:Stats1:ProfileThresholdY_RBV
                #IM1L0:XTES:CAM:Stats1:ProfileCentroidX_RBV
                #IM1L0:XTES:CAM:Stats1:ProfileCentroidY_RBV
                #IM1L0:XTES:CAM:Stats1:ProfileCursorX_RBV
                #IM1L0:XTES:CAM:Stats1:ProfileCursorY_RBV
                print('profile cursor: ',self.imgstat.profile_cursor.get())
                print('profile centroid: ',self.imgstat.profile_centroid.get())
                if self.imgstat.compute_centroid.get() == 'Yes':
                    print('profile threshold: ',self.imgstat.profile_threshold.get())
                    print('profile avergage: ',self.imgstat.profile_average.get())

class AT1L0(Device, BaseInterface):
    energy = EpicsSignalRO('SATT:FEE1:320:ETOA.E', kind='config')
    attenuation = EpicsSignalRO('SATT:FEE1:320:RACT', kind='hinted')
    transmission = EpicsSignalRO('SATT:FEE1:320:TACT', name='normal')
    r_des = EpicsSignal('SATT:FEE1:320:RDES', name='normal')
    r_floor = EpicsSignal('SATT:FEE1:320:R_FLOOR', name='omitted')
    r_ceiling = EpicsSignal('SATT:FEE1:320:R_CEIL', name='omitted')
    trans_floor = EpicsSignal('SATT:FEE1:320:T_FLOOR', name='omitted')
    trans_ceiling = EpicsSignal('SATT:FEE1:320:T_CEIL', name='omitted')
    go = EpicsSignal('SATT:FEE1:320:GO', name='omitted')
    
    def setR(self, att_des, ask=False, wait=True):
        self.att_des.put(att_des)
        if ask:
            print('possible ratios: %g (F) -  %g (C)'%(self.r_floor, self.r_ceiling))
            answer=raw_input('F/C? ')
        if answer=='C':
            self.go.put(2)
            if wait: time.sleep(5)
        else:
            self.go.put(3)
            if wait: time.sleep(5)        

class User():
    def __init__(self):
        self.im3l0_ppm_record = PPM_Record()
        try:
            self.im1l0_h5 = ImagerHdf5(camviewer.im1l0)
            self.im2l0_h5 = ImagerHdf5(camviewer.im2l0)
            self.im3l0_h5 = ImagerHdf5(camviewer.im3l0)
            self.im4l0_h5 = ImagerHdf5(camviewer.im4l0)
            self.im1l0_stats = ImagerStats(camviewer.im1l0)
            self.im2l0_stats = ImagerStats(camviewer.im2l0)
            self.im3l0_stats = ImagerStats(camviewer.im3l0)
            self.im4l0_stats = ImagerStats(camviewer.im4l0)
        except:
            self.im1l0_h5 = None
            self.im2l0_h5 = None
            self.im3l0_h5 = None
            self.im4l0_h5 = None
            self.im1l0_stats = None
            self.im2l0_stats = None
            self.im3l0_stats = None
            self.im4l0_stats = None
        self.ao15 = EpicsSignal('XCS:USR:ao1:15', name='ao15')
        self.at1l0 = AT1L0(name='at1l0')
        ##does not work right now.
        #self.amiao15 = AmiDet('testVar_ao', name='amiao15')

    def savePowermeter(self, colltime=None, rate=None, filename=None, pwm=None):
        if pwm is None: pwm = self.im3l0_ppm_record
        if colltime is not None:
            pwm.setCollectionTime(colltime)
        if filename is not None:
            pwm.setFilename(filename)
        else:
            basename = pwm.pvname.split(':')[0]+'_powermeter'
            expname = check_output('get_curr_exp').decode('utf-8').replace('\n','')
            try:
                runnr = int(check_output('get_lastRun').decode('utf-8').replace('\n',''))
            except:
                runnr=0
            dirname = '/reg/neh/operator/%sopr/experiments/%s'%(expname[:3], expname)
            pwm.setFilename('%s/powermeterData/%s_Run%03d_%s.data'%(dirname,expname, runnr+1, basename))
        #pwm.collectData(rate=rate)
        #pwm.writeFile()
        print('Wrote %d seconds of powermeter data to %s'%(pwm.collection_time,pwm.filename))

    def takeRun(self, nEvents, record=True):
        daq.configure(events=120, record=record)
        daq.begin(events=nEvents)
        daq.wait()
        daq.end_run()

    def get_ascan(self, motor, start, end, nsteps, nEvents, record=True):
        daq.configure(nEvents, record=record, controls=[motor])
        return scan([daq], motor, start, end, nsteps)

    def get_dscan(self, motor, start, end, nsteps, nEvents, record=True):
        daq.configure(nEvents, record=record)
        currPos = motor.wm()
        return scan([daq], motor, currPos+start, currPos+end, nsteps)

    def ascan_wimagerh5(self, imagerh5, motor, start, end, nsteps, nEvents, record=True):
        daq.configure(nEvents, record=record, controls=[motor])
        this_plan = scan([daq], motor, start, end, nsteps)
        #we assume DAQ runs at 120Hz (event code 40 or 140)
        #       a DAQ transition time of 0.3 seconds
        #       a DAQ start time of about 1 sec
        plan_duration = nsteps*nEvents/120.+0.3*(nsteps-1)+1
        imagerh5.prepare(nSec=plan_duration)
        imagerh5.write()
        RE(this_plan)
        imagerh5.write_wait()
