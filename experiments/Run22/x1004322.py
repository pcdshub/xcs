import numpy as np
import time

from ophyd import EpicsSignal
from ophyd import EpicsSignalRO

from pcdsdevices.beam_stats import BeamEnergyRequest, BeamEnergyRequestACRWait

from xcs.db import xcs_ccm as ccm
from xcs.db import daq


class User():
    def __init__(self):
        self.acr_energy_1 = BeamEnergyRequestACRWait(
            name='acr_energy',
            prefix='XCS',
            acr_status_suffix='AO805'
        ) # AO801 for SXR
        self.acr_energy_2 = BeamEnergyRequestACRWait(
            name='acr_energy',
            prefix='XCS',
            acr_status_suffix='AO805', pv_index=2
        )


    def long_escan(self,
                   energies=[],
                   k_stepsize=0.1,
                   record=False,
                   wait_time=0.2):
        energy_start = ccm.energy_with_vernier.energy()
        k_energy_start = self.acr_energy_2.get().setpoint

        energy_increase = 0
        energy_0 = energies[0]

        try:
            if record == True:
                daq.configure(record=True)
                daq.begin(record=True)

            for energy in energies:
                print(f"Energy: {energy:0.4f}")
                ccm.energy_with_vernier.move(energy)
                e_step = energy - energy_0
                if e_step > k_stepsize:
                    if record == True:
                        daq.pause()
                    k_energy = (energy + k_stepsize/2) * 1000
                    print(f"Moving k to {k_energy:0.0f}")
                    time.sleep(0.5)
                    self.acr_energy_2.move(k_energy)
                    energy_0 = energy
                    if record == True:
                        daq.begin(record=True)
                time.sleep(wait_time)

            if record == True:
                daq.end_run()

        except Exception as e:
            print("Error: ")
            print(e)

        finally:
            print('Returning to initial position')
            ccm.energy_with_vernier.energy.move(energy_start)
            self.acr_energy_2.move(k_energy_start)
        return








