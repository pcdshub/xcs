import logging

import numpy as np
from ophyd.device import Device, Component as Cpt
from ophyd.signal import EpicsSignal
from ophyd.status import wait as status_wait

import xcs.db as db

logger = logging.getLogger(__name__)


class NotepadScanStatus(Device):
    istep = Cpt(EpicsSignal, ":ISTEP")
    isscan = Cpt(EpicsSignal, ":ISSCAN")
    nshots = Cpt(EpicsSignal, ":NSHOTS")
    nsteps = Cpt(EpicsSignal, ":NSTEPS")
    var0 = Cpt(EpicsSignal, ":SCANVAR00")
    var1 = Cpt(EpicsSignal, ":SCANVAR01")
    var2 = Cpt(EpicsSignal, ":SCANVAR02")
    var0_max = Cpt(EpicsSignal, ":MAX00")
    var1_max = Cpt(EpicsSignal, ":MAX01")
    var2_max = Cpt(EpicsSignal, ":MAX02")
    var0_min = Cpt(EpicsSignal, ":MIN00")
    var1_min = Cpt(EpicsSignal, ":MIN01")
    var2_min = Cpt(EpicsSignal, ":MIN02")

    def clean_fields(self):
        for sig_name in self.signal_names:
            sig = getattr(self, sig_name)
            val = sig.value
            if isinstance(val, (int, float)):
                sig.put(0)
            elif isinstance(val, str):
                sig.put('')


notepad_scan_status = NotepadScanStatus('XCS:SCAN', name='xcs_scan_status')


def ascan(motor, start, stop, num, events_per_point=360, record=False,
          controls=None, **kwargs):
    """
    Quick re-implementation of old python for the transition
    """
    daq = db.daq
    events = events_per_point
    status = notepad_scan_status
    status.clean_fields()
    if controls is None:
        controls = {}
    start_pos = motor.position

    def get_controls(motor, extra_controls):
        out_arr = {motor.name: motor}
        out_arr.update(extra_controls)
        return out_arr

    try:
        scan_controls = get_controls(motor, controls)
        daq.configure(record=record, controls=scan_controls)

        status.isscan.put(1)
        status.nshots.put(events_per_point)
        status.nsteps.put(num)
        status.var0.put(motor.name)
        status.var0_max.put(max((start, stop)))
        status.var0_min.put(min((start, stop)))

        for i, step in enumerate(np.linspace(start, stop, num)):
            logger.info('Beginning step {}'.format(step))
            try:
                mstat = motor.set(step, verify_move=False, **kwargs)
            except TypeError:
                mstat = motor.set(step, **kwargs)
            status.istep.put(i)
            status_wait(mstat)
            scan_controls = get_controls(motor, controls)
            daq.begin(events=events, controls=scan_controls)
            logger.info('Waiting for {} events ...'.format(events))
            daq.wait()
    finally:
        logger.info('DONE!')
        status.clean_fields()
        daq.end_run()
        daq.disconnect()
        try:
            motor.set(start_pos, verify_move=False, **kwargs)
        except TypeError:
            motor.set(start_pos, **kwargs)
