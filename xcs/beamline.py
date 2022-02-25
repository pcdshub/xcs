import logging
from hutch_python.utils import safe_load

logger = logging.getLogger(__name__)

#all commented out for FeeComm(Test)

with safe_load('Split and Delay'):
   from hxrsnd.sndsystem import SplitAndDelay
   from xcs.db import daq, RE
   snd = SplitAndDelay('XCS:SND', name='snd', daq=daq, RE=RE)
 

#this should remain OUT!
#with safe_load('SnD ascan shortcut'):
#    from xcs.snd_scripts import ascan
#this should remain OUT!


with safe_load('Event Sequencer'):
    from pcdsdevices.sequencer import EventSequencer
    seq = EventSequencer('ECS:SYS0:4', name='seq_4')
    seq2 = EventSequencer('ECS:SYS0:11', name='seq_11')

with safe_load('LXE'):
    from pcdsdevices.lxe import LaserEnergyPositioner
    from hutch_python.utils import get_current_experiment
    from ophyd.device import Component as Cpt
    from pcdsdevices.epics_motor import Newport

    # Hack the LXE class to make it work with Newports
    class LXE(LaserEnergyPositioner): 
        motor = Cpt(Newport, '')

    lxe_calib_file = '/reg/neh/operator/xcsopr/experiments/'+get_current_experiment('xcs')+'/wpcalib'

    try:
        lxe = LXE('XCS:LAS:MMN:08', calibration_file=lxe_calib_file, name='lxe')    
    except OSError:
        logger.error('Could not load file: %s', lxe_calib_file)
        raise FileNotFoundError

with safe_load('LXE OPA'):
    from pcdsdevices.lxe import LaserEnergyPositioner
    from hutch_python.utils import get_current_experiment
    from ophyd.device import Component as Cpt
    from pcdsdevices.epics_motor import Newport

    # Hack the LXE class to make it work with Newports
    class LXE(LaserEnergyPositioner): 
        motor = Cpt(Newport, '')

    lxe_opa_calib_file = '/reg/neh/operator/xcsopr/experiments/'+get_current_experiment('xcs')+'/wpcalib_opa'

    try:
        lxe_opa = LXE('XCS:LAS:MMN:04', calibration_file=lxe_opa_calib_file, name='lxe_opa')    
    except OSError:
        logger.error('Could not load file: %s', lxe_opa_calib_file)
        raise FileNotFoundError

with safe_load('More Laser Motors'):
    from pcdsdevices.lxe import LaserEnergyPositioner, LaserTiming, LaserTimingCompensation
    from pcdsdevices.epics_motor import Newport


    #las_wp = Newport('XCS:LAS:MMN:08', name='las_wp')
    las_opa_wp = Newport('XCS:LAS:MMN:04', name='las_opa_wp')
    lens_h = Newport('XCS:LAS:MMN:08', name='lens_h')
    lens_v = Newport('XCS:LAS:MMN:06', name='lens_v')
    lens_f = Newport('XCS:LAS:MMN:07', name='lens_f')
    pol_wp = Newport('XCS:USR:MMN:07', name='pol_wp')

    # It's okay to be a little unhappy, no need to whine about it
#    from ophyd.epics_motor import AlarmSeverity
    import logging
#    lxt_fast.tolerated_alarm = AlarmSeverity.MINOR
    logging.getLogger('pint').setLevel(logging.ERROR)

#with safe_load('Old lxt & lxt_ttc'):
#    from ophyd.device import Component as Cpt
#
#
#    from pcdsdevices.epics_motor import Newport
#    from pcdsdevices.lxe import LaserTiming
#    from pcdsdevices.pseudopos import DelayMotor, SyncAxis, delay_class_factory
#
#    DelayNewport = delay_class_factory(Newport)
#
#    # Reconfigurable lxt_ttc
#    # Any motor added in here will be moved in the group
#    class LXTTTC(SyncAxis):
#        lxt = Cpt(LaserTiming, 'LAS:FS4', name='lxt')
#        txt = Cpt(DelayNewport, 'XCS:LAS:MMN:01',
#                  n_bounces=10, name='txt')
#
#        tab_component_names = True
#        scales = {'txt': -1}
#        warn_deadband = 5e-14
#        fix_sync_keep_still = 'lxt'
#        sync_limits = (-10e-6, 10e-6)
#
#    lxt_ttc = LXTTTC('', name='lxt_ttc')
#    lxt = lxt_ttc.lxt

with safe_load('New lxt & lxt_ttc'):
    from pcdsdevices.device import ObjectComponent as OCpt
    from pcdsdevices.lxe import LaserTiming
    from pcdsdevices.pseudopos import SyncAxis
    from xcs.db import xcs_txt

    lxt = LaserTiming('LAS:FS4', name='lxt')
    xcs_txt.name = 'txt'

    class LXTTTC(SyncAxis):
        lxt = OCpt(lxt)
        txt = OCpt(xcs_txt)

        tab_component_names = True
        scales = {'txt': -1}
        warn_deadband = 5e-14
        fix_sync_keep_still = 'lxt'
        sync_limits = (-10e-6, 10e-6)


    lxt_ttc = LXTTTC('', name='lxt_ttc')


with safe_load('Delay Scan'):
    from ophyd.device import Device, Component as Cpt
    from ophyd.signal import EpicsSignal
    from .delay_scan import delay_scan, USBEncoder
    lxt_fast_enc = USBEncoder('XCS:USDUSB4:01:CH0',name='lxt_fast_enc')

with safe_load('Other Useful Actuators'):
    from pcdsdevices.epics_motor import IMS
    from ophyd.signal import EpicsSignal
    tt_ty = IMS('XCS:SB2:MMS:46',name='tt_ty')
    lib_y = IMS('XCS:USR:MMS:04',name='lib_y')
    det_y = IMS('XCS:USR:MMS:40',name='det_y')
    
    from xcs.devices import LaserShutter
    lp = LaserShutter('XCS:USR:ao1:7', name='lp')
    def lp_close():
        lp('IN')
    def lp_open():
        lp('OUT')

#with safe_load('User Opal'):
#    from pcdsdevices.areadetector.detectors import PCDSDetector
#    opal_1 = PCDSDetector('XCS:USR:O1000:01:', name='opal_1')

##these should mot be here with the exception of laser motors until we 
##  have a decent laser module
with safe_load('User Newports'):
    from pcdsdevices.epics_motor import Newport
#    sam_x = Newport('XCS:USR:MMN:01', name='sam_x')
    det_x = Newport('XCS:USR:MMN:08', name='det_x')
#    det_z = Newport('XCS:USR:MMN:16', name='det_z')
    TT_vert = Newport('XCS:USR:MMN:02', name='TT_vert')
    det_z = Newport('XCS:USR:MMN:16', name='det_z')
#    bs_x = Newport('XCS:USR:MMN:03', name='bs_x')
#    JF_x = Newport('XCS:USR:MMN:05', name='JF_x')
#    bs_y = Newport('XCS:USR:MMN:06', name='bs_y')


with safe_load('Polycapillary System'):
    from pcdsdevices.epics_motor import EpicsMotorInterface
    from ophyd.device import Device, Component as Cpt
    from ophyd.signal import Signal

    class MMC(EpicsMotorInterface):
        direction_of_travel = Cpt(Signal, kind='omitted')
    class Polycap(Device):
        m1 = Cpt(MMC, ':MOTOR1', name='motor1')
        m2 = Cpt(MMC, ':MOTOR2', name='motor2')
        m3 = Cpt(MMC, ':MOTOR3', name='motor3')
        m4 = Cpt(MMC, ':MOTOR4', name='motor4')
        m5 = Cpt(MMC, ':MOTOR5', name='motor5')
        m6 = Cpt(MMC, ':MOTOR6', name='motor6')
        m7 = Cpt(MMC, ':MOTOR7', name='motor7')
        m8 = Cpt(MMC, ':MOTOR8', name='motor8')

    polycap = Polycap('BL152:MC1', name='polycapillary')


with safe_load('Roving Spectrometer'):
    from ophyd.device import Device, Component as Cpt
    from pcdsdevices.epics_motor import BeckhoffAxis

    class RovingSpec(Device):
        all_h = Cpt(BeckhoffAxis, ':ALL_H', name='all_h')
        all_v = Cpt(BeckhoffAxis, ':ALL_V', name='all_v')
        xtal_th = Cpt(BeckhoffAxis, ':XTAL_TH', name='xtal_th')
        xtal_tth = Cpt(BeckhoffAxis, ':XTAL_TTH', name='xtal_tth')
        xtal_h = Cpt(BeckhoffAxis, ':XTAL_H', name='xtal_h')
        xtal_v = Cpt(BeckhoffAxis, ':XTAL_V', name='xtal_v')
        det_h = Cpt(BeckhoffAxis, ':DET_H', name='det_h')
        det_v = Cpt(BeckhoffAxis, ':DET_V', name='det_v')
    rov_spec = RovingSpec('HXX:HXSS:ROV:MMS', name='rov_spec')

with safe_load('Liquid Jet'):
    from pcdsdevices.jet import BeckhoffJet
    ljh = BeckhoffJet('XCS:LJH', name='ljh')

#with safe_load('CCM'):
#    from pcdsdevices.ccm import CCM
#    xcs_ccm = CCM(alio_prefix='XCS:MON:MPZ:01', theta2fine_prefix='XCS:MON:MPZ:02',
#                  theta2coarse_prefix='XCS:MON:PIC:05', chi2_prefix='XCS:MON:PIC:06',
#                  x_down_prefix='XCS:MON:MMS:24', x_up_prefix='XCS:MON:MMS:25',
#                  y_down_prefix='XCS:MON:MMS:26', y_up_north_prefix='XCS:MON:MMS:27',
#                  y_up_south_prefix='XCS:MON:MMS:28', in_pos=3.3, out_pos=13.18,
#                  name='xcs_ccm')
                
#
# this all thould go and we should start using the questionnaire.
# that's what it's goe.
#


with safe_load('Timetool'):
    from pcdsdevices.timetool import TimetoolWithNav
    tt = TimetoolWithNav('XCS:SB2:TIMETOOL', name='xcs_timetool', prefix_det='XCS:GIGE:08')

#this is XCS: we have scan PV as each hutch should!
with safe_load('Scan PVs'):
    from xcs.db import scan_pvs
    scan_pvs.enable()

with safe_load('XFLS Motors (Temporary)'):
    from ophyd import Device, Component as Cpt
    from pcdsdevices.epics_motor import IMS
    from pcdsdevices.interface import BaseInterface
    class XFLS(BaseInterface, Device):
        x = Cpt(IMS, ':MMS:22', name='x')
        y = Cpt(IMS, ':MMS:23', name='y')
        z = Cpt(IMS, ':MMS:24', name='z')
    crl2 = XFLS('XCS:SB2', name='xcs_xfls')

with safe_load('Create Aliases'):
    #from xcs.db import at2l0
    #at2l0_alias=at2l0
    #from xcs.db import sb1
    #create some old, known aliases
    from xcs.db import hx2_pim as  xppyag1
    from xcs.db import um6_pim as yag1
    from xcs.db import hxd_dg2_pim as  yag2
    from xcs.db import xcs_dg3_pim as  yag3
    from xcs.db import xrt_dg3m_pim as  yag3m
    from xcs.db import xcs_sb1_pim as  yag4
    from xcs.db import xcs_sb2_pim as yag5

    from xcs.db import um6_ipm as ipm1
    from xcs.db import hxd_dg2_ipm as ipm2
    from xcs.db import xcs_dg3_ipm as ipm3
    from xcs.db import xcs_sb1_ipm as ipm4
    from xcs.db import xcs_sb2_ipm as ipm5

    from xcs.db import hx2_slits as xpps1
    from xcs.db import um6_slits as s1
    from xcs.db import hxd_dg2_slits as  s2
    from xcs.db import xcs_dg3_slits as s3
    from xcs.db import xrt_dg3m_slits as s3m
    from xcs.db import xcs_sb1_slits as s4
    from xcs.db import xcs_sb2_upstream_slits as s5
    from xcs.db import xcs_sb2_downstream_slits as s6

    from xcs.db import at1l0 as fat1
    from xcs.db import at2l0 as fat2	

    from xcs.db import xcs_attenuator as att
    from xcs.db import xcs_pulsepicker as pp
    from xcs.db import xcs_gon as gon

    from xcs.db import xcs_txt as txt
    from xcs.db import xcs_lxt_fast as lxt_fast

    from xcs.db import xcs_lodcm as lom
    from xcs.db import xcs_ccm as ccm
    #from xcs.db import xcs_xfls as crl2
    from xcs.db import xcs_pfls as crl1

    from xcs.db import xcs_samplestage
    gon_sx = xcs_samplestage.x
    gon_sy = xcs_samplestage.y
    gon_sz = xcs_samplestage.z

    ccmE = ccm.energy
    ccmE.name = 'ccmE'
    ccmE_vernier = ccm.energy_with_vernier
    ccmE_vernier.name = 'ccmE_vernier'

with safe_load('Pink/Mono Offset'):
    from xcs.beamline_offset import pinkmono
    pinkmono.beamline_mono_offsets = {
        'default': 7.5,
        yag3: 'default',
        yag4: 'default',
        yag5: 'default',
        ipm3: 'default',
        ipm4: 'default',
        ipm5: 'default',
        s3: 'default',
        s4: 'default',
        s5: 'default',
        s6: 'default',
        lib_y: 'default'
    }

#with safe_load('Syringe Pump'):
#    #from xcs.syringepump import SyringePump
#    from xcs.devices import SyringePump
#    syringepump=SyringePump('solvent_topup',"XCS:USR:ao1:0","XCS:USR:ao1:1")

with safe_load('Syringe_Pump'):
    #from xcs.syringepump import SyringePump
    from xcs.devices import Syringe_Pump
    syringe_pump=Syringe_Pump()

with safe_load('import macros'):
    from xcs.macros import *

with safe_load('pyami detectors'):
    #from socket import gethostname
    #if gethostname() == 'xcs-daq':
    from xcs.ami_detectors import *
    #else:
        #logger.info('Not on xcs-daq, failing!')
        #raise ConnectionError

with safe_load('bluesky setup'):
    from bluesky.callbacks.mpl_plotting import initialize_qt_teleporter
    initialize_qt_teleporter()

with safe_load('ladm_det'):
    xcsdet_y = IMS('XCS:LAM:MMS:07',name = 'xcsdet_y')
    xcsdet_x = IMS('XCS:LAM:MMS:06',name = 'xcsdet_x')

with safe_load('LADM'):
    from pcdsdevices.ladm import LADM, LADMMotors, Beamstops
    from pcdsdevices.positioner import FuncPositioner
    lm = LADMMotors('XCS:LAM', name='ladm_motors')
    bs = Beamstops('XCS:LAM', name='ladm_beamstops')
    theta_pv = EpicsSignal('XCS:VARS:LAM:Theta', name = 'LADM_theta')
    gamma_pv = EpicsSignal('XCS:VARS:LAM:Gamma', name='LADM_gamma')     
    ladm = LADM(
                lm.x1_us,
                lm.y1_us,
                lm.x2_ds, 
                lm.y2_ds,
                lm.z_us,
                theta_pv, gamma_pv
               )
    ladmTheta = FuncPositioner(name='ladmTheta',move=ladm.moveTheta,get_pos=ladm.wmTheta,set_pos=ladm.setTheta)
    ladm.theta = ladmTheta
    ladmXT = FuncPositioner(name='ladmXT',move=ladm.moveX, get_pos=ladm.wmX, set_pos=ladm._setX, egu='mm', limits=(ladm._get_lowlimX, ladm._get_hilimX))
    ladm.XT = ladmXT
    
    #ladm.__lowlimX=ladm._set_lowlim(-10)
    #ladm.__hilimX=ladm._set_hilim(2000)
    
with safe_load('drift monitor'):
   import numpy as np
   import json
   import sys
   import time
   import os
   import socket
   import logging
   class drift():
      def drift_log(idata):
         savefilename = "/cds/home/opr/xcsopr/experiments/xcsl2619/drift_log.txt"
         currenttime = time.ctime()
         out_f = open(savefilename,'a')
         out_f.write(str(idata)+ "," + currenttime.split(" ")[3] +"\n")
         out_f.close()

      def tt_rough_FB(ttamp_th = 0.02, ipm4_th = 500, tt_window = 0.05):
         fbvalue = 0 # for drift record
         while(1):
            tenshots_tt = np.zeros([1,])
            dlen = 0
            while(dlen < 61):
               #ttcomm = Popen("caget XPP:TIMETOOL:TTALL",shell = True, stdout=PIPE)
               #ttdata = (ttcomm.communicate()[0]).decode()
               ttall = EpicsSignal('XCS:TIMETOOL:TTALL')
               ttdata = ttall.get()
                
               current_tt = ttdata[1,]
               ttamp = ttdata[2,]
               ipm4val = ttdata[3,]
               ttfwhm = ttdata[5,]
               #current_tt = float((ttdata.split(" "))[3])
               #ttamp = float((ttdata.split(" "))[4])
               #ipm2val = float((ttdata.split(" "))[5])
               #ttfwhm = float((ttdata.split(" "))[7])
               if(dlen%10 == 0):
                  #print("tt_value",current_tt,"ttamp",ttamp,"ipm4",ipm4val)
                  print("tt_value:%0.3f" %current_tt + "   ttamp:%0.3f " %ttamp +"   ipm4:%d" %ipm4val)
               if (ttamp > ttamp_th)and(ipm4val > ipm4_th)and(ttfwhm < 130)and(ttfwhm >  30)and(current_tt != tenshots_tt[-1,]):# for filtering the last one is for when DAQ is stopping
                  tenshots_tt = np.insert(tenshots_tt,dlen,current_tt)
                  dlen = np.shape(tenshots_tt)[0]
               time.sleep(0.01)
            tenshots_tt = np.delete(tenshots_tt,0)
            ave_tt = np.mean(tenshots_tt)
            print("Moving average of timetool value:", ave_tt)
    
            if np.abs(ave_tt) > tt_window:
               ave_tt_second=-(ave_tt*1e-12)
               lxt.mvr(ave_tt_second)
               print("feedback %f ps"%ave_tt)
               fbvalue = ave_tt + fbvalue
               #drift_log(str(fbvalue))
         return
     
     
  
      def pid_control(kp,ki,kd,ave_data,faketime):
         fd_value = kp*ave_data[0,] + ki*(np.sum(ave_data[:,]))+kd*((ave_data[1,]-ave_data[0,])/faketime)
         return fd_value
      def matlabPV_FB(feedbackvalue):#get and put timedelay signal
         matPV = EpicsSignal('LAS:FS4:VIT:matlab:04')
         org_matPV = matPV.get()#the matlab PV value before FB
         fbvalns = feedbackvalue * 1e+9#feedback value in ns
         fbinput = org_matPV + fbvalns#relative to absolute value
         matPV.put(fbinput)
         return
      def get_ttall():#get timetool related signal
         ttall = EpicsSignal('XCS:TIMETOOL:TTALL')
         ttdata = ttall.get()
         current_tt = ttdata[1,]
         ttamp = ttdata[2,]
         ipm4val = ttdata[3,]
         ttfwhm = ttdata[5,]
         return current_tt, ttamp, ipm4val, ttfwhm
      def tt_recover(scanrange = 5e-12,stepsize = -0.5e-12,direction = "p",testshot = 240):#For tt_signal recover in 10 ps
         #las.tt_y.umv(54.67)#LuAG to find tt signal
         originaldelay = lxt()
         if direction == "p":
            print("Search tt signal from positive to negative")
            lxt.mvr(scanrange)
            time.sleep(0.5)
         elif direction == "n":
            lxt.mvr(-1*scanrange)
            print("Search tt signal from negative to positive")
            stepsize = -1 * stepsize
            time.sleep(0.5)
         j = 0
         while(abs(stepsize * j) < abs(scanrange * 2) ):
            ttdata = np.zeros([testshot,])
            ii = 0
            for ii in range(testshot):
               current_tt, ttamp, ipm2val, ttfwhm = drift.get_ttall()#get 240 shots to find timetool signal
               if (ttamp > 0.03)and(ttfwhm < 130)and(ttfwhm >  70)and(ttamp<2):
                  ttdata[ii,] = ttamp
                  time.sleep(0.008)
            print(ttdata)
            if np.count_nonzero(ttdata[:,]) > 30:#1/4 shots have timetool signal
               print("Found timetool signal and set current lxt to 0")
               print(f"we will reset the current {lxt()} position to 0")
               lxt.set_current_position(0)
               #las.tt_y.umv(67.1777)#Switch to YAG
               print("Please run las.tt_rough_FB()")
               ttfb = input("Turn on feedback? yes(y) or No 'any other' ")
               if ((ttfb == "yes") or (ttfb == "y")):
                  print("feedback on")
                  drift.tt_rough_FB(kp= 0.2,ki=0.1)
               else:
                  print("No feedback yet")
               return
            else:
               lxt.umvr(stepsize)
               time.sleep(0.5)
               print(f"searching timetool signal {lxt()}")
            j = j + 1          
            print("The script cannot find the timetool signal in this range. Try las.tt_find()")        
          
        
            return

         def tt_find(ini_delay = 10e-9):#tt signal find tool the ini_delay is now input argument
            if lxt() != 0:
               print('\033[1m'+ "Set current position to 0 to search" + '\033[0m') 
               return
            elif lxt() ==0:
               #las.tt_y.umv(54.67)#LuAG to find tt signal
               delayinput = ini_delay#Search window
               i = 0#iteration time
               while(1):#20ns search until finding the correlation switched
                  print('\033[1m'+ "Can you see 'The positive correlation(p)' or 'The negative correlation(n)?' p/n or quit this script q"+'\033[0m')
                  bs = input()#input the current correlation
                  if i == 0:# for the initialization
                     prebs = bs

                  if (i < 10)and(prebs == bs):#First search in 100 ns. 100 ns is too large. If cannot find in 10 iteration need to check the other side
                     if bs == "p":
                        delayinput = -1 * abs(delayinput)
                        lxt.mvr(delayinput)
                        i = i + 1
                        print(f"Searching the negative correlation with 10ns. Number of iteration:{i}")
                     elif bs == "n":#find non-correlation
                        delayinput = abs(delayinput)
                        lxt.mvr(delayinput)
                        i = i + 1
                        print(f"Searching the positive or no correlation with 10ns. Number of iteration:{i}")
                     elif bs == "q":
                        print("Quit")
                        return
                     else:
                        print('\033[1m'+"Can you see 'The positive correlation(p)'or'The negative correlation(n)?' p/n or quit this script q" + '\033[0m')
                  elif (prebs != bs):
                     print('\033[1m'+"Switch to binary search"+'\033[0m')
                     break
                  prebs = bs#the correlation change?


with safe_load('gige hdf5 beta'):
    from pcdsdevices.areadetector.detectors import PCDSHDF5BlueskyTriggerable
    xcs_gige_lj1_hdf5 = PCDSHDF5BlueskyTriggerable(
        'XCS:GIGE:LJ1:',
        name='xcs_gige_lj1_hdf5',
        write_path='/cds/data/iocData/ioc-xcs-gige-lj1',
    )

def snd_park():
    with safe_load('Split and Delay'):
        from hxrsnd.sndsystem import SplitAndDelay
        from xcs.db import daq, RE
    snd = SplitAndDelay('XCS:SND', name='snd', daq=daq, RE=RE)
    snd.t1.L.mv(250,wait = True)
    snd.t4.L.mv(250,wait = True)

    snd.dd.x.mv(-270,wait = False)
    snd.di.x.mv(-90,wait = False)
    snd.do.x.mv(-100,wait = False)
    snd.dci.x.mv(70,wait = False)
    snd.dco.x.mv(70,wait = False)
    snd.dcc.x.mv(120,wait = False)

    snd.t1.tth.mv(0,wait = True)
    snd.t4.tth.mv(0,wait = True)

    snd.t2.x.mv(70,wait = False)

    snd.t1.x.mv(90)
    snd.t4.x.mv(90)

    snd.t3.x.mv(70)
    return True
