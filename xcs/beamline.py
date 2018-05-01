from hutch_python.utils import safe_load


with safe_load('Split and Delay'):
    from hxrsnd.sndsystem import SplitAndDelay
    from xcs.db import daq, RE
    snd = SplitAndDelay('XCS:SND', daq=daq, RE=RE)


with safe_load('SnD ascan shortcut'):
    from xcs.snd_scripts import ascan


with safe_load('Event Sequencer'):
    from pcdsdevices.sequencer import EventSequencer
    seq = EventSequencer('ECS:SYS0:4', name='seq_4')


with safe_load('User Opal'):
    from pcdsdevices.areadetector.detectors import DefaultAreaDetector
    opal_1 = DefaultAreaDetector('XCS:USR:O1000:01', name='opal_1')


with safe_load('User Newports'):
    from pcdsdevices.epics_motor import Newport
    sam_x = Newport('XCS:USR:MMN:01', name='sam_x')
    sam_y = Newport('XCS:USR:MMN:02', name='sam_y')
