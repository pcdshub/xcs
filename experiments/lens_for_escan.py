from ophyd.device import Component as Cpt
from ophyd.pseudopos import PseudoSingle

from pcdsdevices.device import ObjectComponent as OCpt
from pcdsdevices.interface import FltMvInterface
from pcdsdevices.pseudopos import (PseudoPositioner, PseudoSingleInterface,
                                   pseudo_position_argument, real_position_argument)

from pcdsdevices import lens
from pcdsdevices.beam_stats import LCLS

import pcdscalc.be_lens_calcs as be

from xcs.db import xcs_attenuator as att
from xcs.db import xcs_ccm as ccm
from xcs.db import xcs_pulsepicker as pp

lcls = LCLS()

#stack1 = [1, 100e-6, 1, 200e-6, 1, 500e-6]
#stack2 = [1, 100e-6, 1, 200e-6, 1, 500e-6, 1, 2000e-6, 3, 3000e-6]
path = "/cds/group/pcds/pyps/apps/hutch-python/xcs/experiments/lens_set_xcsx1008722"


#be.configure_defaults(distance=3.852, fwhm_unfocused=500e-6)  # xpp
be.configure_defaults(distance=3.246, fwhm_unfocused=300e-6)  # xcs


def make_stack():
    return lens.LensStack(
                x_prefix = 'XCS:SB2:MMS:22',
                y_prefix = 'XCS:SB2:MMS:23',
                z_prefix = 'XCS:SB2:MMS:24',
                z_offset = 3.246, # xcs IP distance to lens_z=0
                z_dir = -1,
                E = None,
                lcls_obj = lcls,
                mono_obj = ccm,
                #att_obj = att,
                att_obj = pp,
                path = path,
                name = 'lens_stack'
            )

lens_stack = make_stack()
lens_stack.set_lens_set(1)


class CcmLens(FltMvInterface, PseudoPositioner):
    _real = ("ccm_energy", "beam_size")
    _pseudo = ("energy", )

    #ccm_energy = OCpt(ccm.energy.energy)
    ccm_energy = OCpt(ccm.energy_with_acr_status.energy)
    beam_size = OCpt(lens_stack.beam_size)

    energy = Cpt(PseudoSingleInterface, egu='keV', kind='hinted')

    tab_whitelist = ['calc_lens_pos', 'ccm', 'stack']
    tab_component_names = True

    def __init__(self, ccm, lens_stack, desired_beamsize=5e-6, *args, **kwargs):
        self.ccm = ccm
        self.stack = lens_stack
        self.desired_beamsize = desired_beamsize
        super().__init__(*args, **kwargs)

    @pseudo_position_argument
    def forward(self, pseudo_pos):
        return self.RealPosition(ccm_energy=pseudo_pos.energy,
                                 beam_size=self.desired_beamsize)

    @real_position_argument
    def inverse(self, real_pos):
        return self.PseudoPosition(energy=real_pos.ccm_energy)

    @pseudo_position_argument
    def move(self, position, *args, **kwargs):
        self.stack.energy = position.energy
        st = super().move(position, *args,
                          moved_cb=self.cb_open_beamstop,
                          **kwargs)
        return st

    def calc_lens_pos(self, energy):
        """
        Return the expected lens position (x,y,z) for a given energy.
        """
        stack_current_energy = self.stack.energy
        #self.stack._E
        if self.stack._which_E != 'User':
            stack_current_energy = None
        self.stack.energy = energy
        lens_pos = self.stack.forward(beam_size=self.desired_beamsize)
        self.stack.energy = stack_current_energy
        return lens_pos

    def cb_open_beamstop(self, obj):
        """
        Callback function to open the attenuator at the end of a move.
        If the atttenuator is used, this function assumes that the blade 9
        is used to block the beam.
        """
        if 'Attenuator' in str(type(self.stack._att_obj)):
            self.stack._att_obj.filters[9].remove()
        elif 'PulsePicker' in str(type(self.stack._att_obj)):
            self.stack._att_obj.open()
        return

    def _concurrent_move(self, real_pos, **kwargs):
        """
        Try done fix: override the waiting list with the pseudopos parents,
        not pseudosingle, since cb is called on the parent in this case
        """
        for real_axis in self._real:
            if isinstance(real_axis, PseudoSingle):
                self._real_waiting.append(real_axis.parent)
            else:
                self._real_waiting_append(real_axis)

        for real, value in zip(self._real, real_pos):
            self.log.debug("[concurrent] Moving %s to %s", real.name, value)
            real.move(value, wait=False, moved_cb=self._real_finished, **kwargs)


