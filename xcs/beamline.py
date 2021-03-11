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
        lxe = LXE('XCS:LAS:MMN:04', calibration_file=lxe_opa_calib_file, name='lxe_opa')    
    except OSError:
        logger.error('Could not load file: %s', lxe_opa_calib_file)
        raise FileNotFoundError

with safe_load('More Laser Motors'):
    from pcdsdevices.lxe import LaserEnergyPositioner, LaserTiming, LaserTimingCompensation
    from pcdsdevices.epics_motor import Newport

    lens_h = Newport('XCS:LAS:MMN:05', name='lens_h')
    lens_v = Newport('XCS:LAS:MMN:06', name='lens_v')
    lens_f = Newport('XCS:LAS:MMN:07', name='lens_f')
    pol_wp = Newport('XCS:USR:MMN:07', name='pol_wp')

    #lxt_ttc = LaserTimingCompensation('', delay_prefix='XCS:LAS:MMN:01', laser_prefix='LAS:FS4', name='lxt_ttc')
    #lxt_ttc.delay.n_bounces = 10

    #lxt = lxt_ttc.laser

    # It's okay to be a little unhappy, no need to whine about it
#    from ophyd.epics_motor import AlarmSeverity
    import logging
#    lxt_fast.tolerated_alarm = AlarmSeverity.MINOR
    logging.getLogger('pint').setLevel(logging.ERROR)

with safe_load('New lxt & lxt_ttc'):
    from ophyd.device import Component as Cpt

    from pcdsdevices.epics_motor import Newport
    from pcdsdevices.lxe import LaserTiming
    from pcdsdevices.pseudopos import DelayMotor, SyncAxis, delay_class_factory

    DelayNewport = delay_class_factory(Newport)

    # Reconfigurable lxt_ttc
    # Any motor added in here will be moved in the group
    class LXTTTC(SyncAxis):
        lxt = Cpt(LaserTiming, 'LAS:FS4', name='lxt')
        txt = Cpt(DelayNewport, 'XCS:LAS:MMN:01',
                  n_bounces=10, name='txt')

        tab_component_names = True
        scales = {'txt': -1}
        warn_deadband = 5e-14
        fix_sync_keep_still = 'lxt'
        sync_limits = (-10e-6, 10e-6)

    lxt_ttc = LXTTTC('', name='lxt_ttc')
    lxt = lxt_ttc.lxt

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
    lp = EpicsSignal('XCS:USR:ao1:7',name='lp')
    def lp_close():
        lp.put('IN')
    def lp_open():
        lp.put('OUT')

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
                
with safe_load('User Dumb Motor'):
    from pcdsdevices.epics_motor import IMS	
    top_slit_x = IMS('XCS:USR:MMS:33', name='top_slit_x')
    top_slit_y = IMS('XCS:USR:MMS:34', name='top_slit_y')
    bot_slit_x = IMS('XCS:USR:MMS:35', name='bot_slit_x')
    #1z = IMS('XCS:USR:MMS:36', name='1z')
    jet_z = IMS('XCS:USR:MMS:41', name='jet_z')
    #mirror_y = IMS('XCS:USR:MMS:48', name='mirror_y')
    #sam_x = IMS('XCS:USR:MMS:44', name='sam_x')
    #sam_y = IMS('XCS:USR:MMS:43', name='sam_y')
    #sam_th = IMS('XCS:USR:MMS:45', name='sam_th')	
    #huber_Rx = IMS('XCS:USR:MMS:32', name='huber_Rx')
    #huber_x = IMS('XCS:USR:MMS:30', name='huber_x')
    #huber_Ry = IMS('XCS:USR:MMS:29', name='huber_Ry')
    #huber_y = IMS('XCS:USR:MMS:19', name='huber_y')
    bot_slit_y = IMS('XCS:USR:MMS:37', name='bot_slit_y')
    jet_y = IMS('XCS:USR:MMS:38', name='jet_y')
    jet_x = IMS('XCS:USR:MMS:39', name='jet_x')
    det_y = IMS('XCS:USR:MMS:40', name='det_y')
    #jj2hg = IMS('XCS:USR:MMS:25', name='jj2hg')
    #jj2ho = IMS('XCS:USR:MMS:26', name='jj2ho')
    #jj2vg = IMS('XCS:USR:MMS:27', name='jj2vg')
    #jj2vo = IMS('XCS:USR:MMS:28', name='jj2vo')
with safe_load('Timetool'):
    from pcdsdevices.timetool import TimetoolWithNav
    tt = TimetoolWithNav('XCS:SB2:TIMETOOL', name='xcs_timetool', prefix_det='XCS:GIGE:08')

#this is XCS: we have scan PV as each hutch should!
with safe_load('Scan PVs'):
    from xcs.db import scan_pvs
    scan_pvs.enable()


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

    from xcs.db import xcs_attenuator as att
    from xcs.db import xcs_pulsepicker as pp
    from xcs.db import xcs_gon as gon

    from xcs.db import xcs_txt as txt
    from xcs.db import xcs_lxt_fast as lxt_fast

    from xcs.db import xcs_ccm as ccm
    ccmE = ccm.calc.energy
    ccmE.name = 'ccmE'
    ccmE_vernier = ccm.calc.energy_with_vernier
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
