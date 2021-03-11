from hutch_python.utils import safe_load

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


with safe_load('Laser Motors'):
    from pcdsdevices.lxe import LaserEnergyPositioner, LaserTiming
    from pcdsdevices.epics_motor import Newport, DelayNewport
    from ophyd.device import Component as Cpt

    # Hack the LXE class to make it work with Newports
    class LXE(LaserEnergyPositioner): 
        motor = Cpt(Newport, '')

    lxe = LXE('XCS:LAS:MMN:08', calibration_file='/reg/neh/operator/xcsopr/experiments/xcsx39618/wpcalib', name='lxe')
    lxt = LaserTiming('LAS:FS4',name='lxt') 
    lxt._fs_tgt_time.kind = 'hinted'

    txt = DelayNewport('XCS:LAS:MMN:01', name='txt', n_bounces=10)
    lens_h = Newport('XCS:LAS:MMN:05', name='lens_h')
    lens_y = Newport('XCS:LAS:MMN:06', name='lens_y')
    lens_f = Newport('XCS:LAS:MMN:07', name='lens_f')
    lxt_fast = DelayNewport('XCS:LAS:MMN:03', name='lxt_fast_s')

    # It's okay to be a little unhappy, no need to whine about it
    from ophyd.epics_motor import AlarmSeverity
    import logging
    lxt_fast.tolerated_alarm = AlarmSeverity.MINOR
    logging.getLogger('pint').setLevel(logging.ERROR)

with safe_load('Delay Scan'):
    from ophyd.device import Device, Component as Cpt
    from ophyd.signal import EpicsSignal
    from .delay_scan import delay_scan
    class USBEncoder(Device):
        tab_component_names = True
        set_zero = Cpt(EpicsSignal, ':ZEROCNT')
        pos = Cpt(EpicsSignal, ':POSITION')
        scale = Cpt(EpicsSignal, ':SCALE')
        offset = Cpt(EpicsSignal, ':OFFSET')
    lxt_fast_enc = USBEncoder('XCS:USDUSB4:01:CH0',name='lxt_fast_enc')


with safe_load('Other Useful Actuators'):
    from pcdsdevices.epics_motor import IMS
    from ophyd.signal import EpicsSignal
    tt_ty = IMS('XCS:SB2:MMS:46',name='tt_ty')
    lib_y = IMS('XCS:USR:MMS:04',name='lib_y')
    det_y = IMS('XCS:USR:MMS:40',name='det_y')
    lp = EpicsSignal('XCS:USR:ao1:7',name='lp')
    def lp_close():
        lp.put(0)
    def lp_open():
        lp.put(4)

#with safe_load('User Opal'):
#    from pcdsdevices.areadetector.detectors import PCDSDetector
#    opal_1 = PCDSDetector('XCS:USR:O1000:01:', name='opal_1')

##these should mot be here with the exception of laser motors until we 
##  have a decent laser module
with safe_load('User Newports'):
    from pcdsdevices.epics_motor import Newport
    sam_x = Newport('XCS:USR:MMN:01', name='sam_x')
    det_x = Newport('XCS:USR:MMN:08', name='det_x')
    det_z = Newport('XCS:USR:MMN:16', name='det_z')
#    sam_y = Newport('XCS:USR:MMN:02', name='sam_y')


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
                
with safe_load('User Dumb Motor'):
    from pcdsdevices.epics_motor import IMS
    test_motor = IMS('XCS:USR:MMS:33', name='test_motor')
    test_motor2 = IMS('XCS:USR:MMS:34', name='test_motor2')

#this is XCS: we have scan PV as each hutch should!
with safe_load('Scan PVs'):
    from xcs.db import scan_pvs
    scan_pvs.enable()


with safe_load('Create Aliases'):
    #from xcs.db import at2l0
    #at2l0_alias=at2l0
    #from xcs.db import sb1
    #create some old, known aliases
    from xcs.db import hx2_pim as  yagh2
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

    from xcs.db import xcs_ccm as ccm
    ccmE = ccm.calc.energy
    ccmE_vernier = ccm.calc.energy_with_vernier
    
with safe_load('import macros'):
    from xcs.macros import *

with safe_load('pyami detectors'):
    from socket import gethostname
    import logging
    if gethostname() == 'xcs-daq':
        from xcs.ami_detectors import *
    else:
        logging.getLogger(__name__).info('Not on xcs-daq, failing!')
        raise ConnectionError

with safe_load('bluesky setup'):
    from bluesky.callbacks.mpl_plotting import initialize_qt_teleporter
    initialize_qt_teleporter()
