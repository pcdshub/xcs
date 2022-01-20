import time
from pswww import pypsElog
from psp import Pv
from beamline import *
from exp_util import XCSExp
from blbase.daq_config_device import Dcfg
from psp.caget import caget
from psp.caput import caput
import os
import time


class LakeShore(object):
    def __init__(self, pvname, channel):
        self.pvname = pvname
        self.channel = channel
        self.__temp = Pv.Pv('%s:GET_TEMP_%s'%(pvname, channel))
        self.__temp_unit = Pv.Pv('%s:GET_UNITS_%s'%(pvname, channel))
        self.__temp_unit.set_string_enum(True)


    @property
    def temp(self):
        return self.__temp.get()

    @property
    def egu(self):
        return self.__temp_unit.get()

    def status(self):
        status  = "LakeShore: %s, chan %s\n"%(self.pvname, self.channel)
        status += " temperature: %.3f %s\n"%(self.temp, self.egu)
        return status

    def __repr__(self):
        return self.status()

class Jungfrau(Dcfg):
    """
    Class for the Jungfrau. Provides a way to Jungfrau
    configurations from within a hutch python session.
    """
    def __init__(self, hutch, src, *aliases):
        """
        Programatically sets up get_name and set_name methods during init.
        """
        # Need to pass src if not MfxEndstation.0:Jungfrau.0 - taken care of in script below.
        #In [34]: psana.DetInfo(48,0,43,1)
        # Out[34]: DetInfo(MfxEndstation.0:Jungfrau.1)
        Dcfg.__init__(self, hutch, *aliases, src=src, typeid=0x3006b) 
        self._add_methods("gainMode", "gainMode")
        self._jfGainMode = {'FixedGain1': 1,
                           'FixedGain2': 2,
                           'ForcedGain1': 3,
                           'ForcedGain2': 4,
                           'HighGain0': 5,
                           'Normal': 0}

    def gainName(self, gain=0):
        for key in self._jfGainMode:
            if self._jfGainMode[key]==gain:
                return key
         
    def commit(self):
        """
        Commits all changes to the database using the current stored config dict
        """
        Dcfg.commit(self)

class GasDetector(object):
    def __init__(self, pvname='GDET:FEE1'):
        self.pvname = pvname
        self.__ch0 = Pv.Pv('%s:241:ENRC'%pvname)
        self.__ch0_egu = Pv.Pv('%s:241:ENRC.EGU'%pvname)
        self.__ch0_egu.set_string_enum(True)
        self.__ch1 = Pv.Pv('%s:242:ENRC'%pvname)
        self.__ch1_egu = Pv.Pv('%s:242:ENRC.EGU'%pvname)
        self.__ch1_egu.set_string_enum(True)

    def _average_chan(self, chan, num):
        chan.monitor_start(True)
        # let values accumulate
        time.sleep(num/120.0)
        avg = reduce(lambda x, y: x + y, chan.values[-num:]) / float(num)
        chan.monitor_stop()
        return avg

    def _average_chans(self, num, *chans):
        for chan in chans:
            chan.monitor_start(True)
        # let values accumulate
        time.sleep(num/120.0)
        avgs = [ reduce(lambda x, y: x + y, chan.values[-num:]) / float(num) for chan in chans]
        for chan in chans:
            chan.monitor_stop()
        return avgs

    def energy_24_avg(self, num):
        return self._average_chans(num, self.__ch0, self.__ch1)

    def energy_36_avg(self, num):
        return self._average_chans(num, self.__ch2, self.__ch3)

    @property
    def energy_241(self):
        return self.__ch0.get()

    def energy_241_avg(self, num):
        return self._average_chan(self.__ch0, num)

    @property
    def units_241(self):
        return self.__ch0_egu.get()

    @property
    def energy_242(self):
        return self.__ch1.get()

    def energy_242_avg(self, num):
        return self._average_chan(self.__ch1, num)

    @property
    def units_242(self):
        return self.__ch1_egu.get()


class Pirani(object):
    def __init__(self, pvname):
        self.pvname = pvname
        self.__pressure = Pv.Pv('%s:PMON'%pvname)
        self.__state = Pv.Pv('%s:STATUSMON'%pvname)
        self.__state.set_string_enum(True)
        self.__pres_status = Pv.Pv('%s:PSTATMON'%pvname)
        self.__pres_status.set_string_enum(True)

    @property
    def pressure(self):
        return self.__pressure.get()

    @property
    def state(self):
        return self.__state.get()

    @property
    def pres_status(self):
        return self.__pres_status.get()

    def status(self):
        status  = "Pressure Gauge: %s\n"%self.pvname
        status += " pressure: %.2g Torr\n"%self.pressure
        status += " gauge state: %s\n"%self.state
        status += " pressure state: %s\n"%self.pres_status
        return status

    def __repr__(self):
        return self.status()


class ColdCathode(object):
    def __init__(self, pvname):
        self.pvname = pvname
        self.__pressure = Pv.Pv('%s:PMON'%pvname)
        self.__state = Pv.Pv('%s:STATE'%pvname)
        self.__state.set_string_enum(True)
        self.__pres_status = Pv.Pv('%s:PSTATMON'%pvname)
        self.__pres_status.set_string_enum(True)

    @property
    def pressure(self):
        return self.__pressure.get()

    @property
    def state(self):
        return self.__state.get()

    @property
    def pres_status(self):
        return self.__pres_status.get()

    def status(self):
        status  = "Pressure Gauge: %s\n"%self.pvname
        status += " pressure: %.2g Torr\n"%self.pressure
        status += " high voltage state: %s\n"%self.state
        status += " pressure state: %s\n"%self.pres_status
        return status

    def __repr__(self):
        return self.status()


class PulsedMagnet(object):
    def __init__(self, evr, width=None, delay=None, polarity=None, pirani=None, cc=None, temp_mon=None):
        self.evr = evr
        self.pirani = pirani
        self.cc = cc
        self.temp_mon = temp_mon
        if width is not None:
            self.evr.width(width)
        if delay is not None:
            self.evr.delay(delay)
        if polarity is not None:
            self.evr.polarity(polarity)

    @property
    def eventcode(self):
        return self.evr.eventcode()

    @eventcode.setter
    def eventcode(self, eventcode):
        self.evr.eventcode(eventcode)

    @property
    def delay(self):
        return self.evr.delay()

    @delay.setter
    def delay(self, delay):
        self.evr.delay(delay)

    @property
    def width(self):
        return self.evr.width()

    @width.setter
    def width(self, width):
        self.evr.width(width)

    @property
    def polarity(self):
        return self.evr.polarity()

    @polarity.setter
    def polarity(self, polarity):
        self.evr.polarity(polarity)

    def status(self):
        status  = "Pulsed Magnet:\n"
        status += "EVR Info -- " + self.evr.status()
        if self.pirani is not None:
            status += self.pirani.status()
        if self.cc is not None:
            status += self.cc.status()
        if self.temp_mon is not None:
            status += "Temp: %.3f %s\n"%(self.temp_mon.temp, self.temp_mon.egu)
        return status

    def __repr__(self):
        return self.status()

class USER(XCSExp):
    def __init__(self):
        expname = os.path.basename(__file__.split(".")[0][3:])
        XCSExp.__init__(self, expname=expname)
        # If the next line fails, we forgot to put a motor into the epicsArch file!
        self.motors = {
            "mag_x": self.mag_x,
            "mag_z": self.mag_z,
            "sam_x": self.sam_x,
            "sam_y": self.sam_y,
            "sam_z": self.sam_z,
            "sam_r": self.sam_r,
            "det_x": self.det_x,
            "det_y": self.det_y,
#            "nav_zoom" : self.nav_zoom,
#            "nav_focus" : self.nav_focus,
        }
        self.mag_pirani = Pirani('XCS:USR:GPI:01')
        self.mag_cc = ColdCathode('XCS:USR:GCC:01')
        self.sample_temp = LakeShore('XCS:USR:TCT:02', 'A')
        self.mag_temp = LakeShore('XCS:USR:TCT:02', 'B')
        self.mag = PulsedMagnet(xcsevrusr1, pirani=self.mag_pirani, cc=self.mag_cc, temp_mon=self.mag_temp)
        self.ttl_high = 2.0
        self.ttl_low = 0.8
        self._ready_sig = Pv.Pv('XCS:USR:ai1:0')
        # gdet threshold to use (mJ)
        self._gdet_threshold_pv = Pv.Pv('XCS:VARS:J78:GDET_THRES')
        self.gdet_avg_count = 30
        self.gdet_mag_retry = 10
#        self.gige1 = gige1
#        self.gige2 = gige2
#        self.gige3 = gige3
#        self.gige4 = gige4
        self.gdet = GasDetector()
        self._bykik_pv = Pv.Pv('IOC:IN20:EV01:BYKIK_ABTACT')
        self._bykik_pv.set_string_enum(True)
        self._req_burst_rate = 'Full'
        self._test_burst_rate = Pv.Pv('PATT:SYS0:1:TESTBURSTRATE')
        self._test_burst_rate.set_string_enum(True)
        self._mps_burst_rate = Pv.Pv('PATT:SYS0:1:MPSBURSTRATE')
        self._mps_burst_rate.set_string_enum(True)
        # number of seconds to pause between empty and magnet
        self.pause_time = 2. #was 0.5, but did not work for xcsl4116, needed more time
        self._min_empty_delay = 4
        self._pp = pp
        self._pp_state = Pv.Pv('XCS:SB2:MMS:09:SE')
        self._pp_state.set_string_enum(True)
        self._seq = event
        self._daq = daq
        self._att = xcsatt
        self.hutch='xcs'
        self.aliases=['BEAM']
        self.gainmodes = ['Normal','ForcedGain1','ForcedGain2']

    @property
    def bykik(self):
        return self._bykik_pv.get()

    def bykik_enable(self):
        self._bykik_pv.put('Enable')

    def bykik_disable(self):
        self._bykik_pv.put('Disable')

    @property
    def machine_burst_rate(self):
        if self._seq.is_beam_owner():
            return self._mps_burst_rate.get()
        else:
            return self._test_burst_rate.get()

    @machine_burst_rate.setter
    def machine_burst_rate(self, rate):
        if self._seq.is_beam_owner():
            self._mps_burst_rate.put(rate)
        else:
            self._test_burst_rate.put(rate)

    def check_burst_rate(self):
        if self.machine_burst_rate != self._req_burst_rate:
            printnow('Machine burst frequency not set to %s! - fixing ... '%self._req_burst_rate)
            self.machine_burst_rate = self._req_burst_rate
            if self._seq.is_beam_owner():
                self._mps_burst_rate.wait_for_value(self._req_burst_rate)
            else:
                self._test_burst_rate.wait_for_value(self._req_burst_rate)
            printnow('done.')

    @property
    def ready_sig(self):
        return self._ready_sig.get()

    @property
    def gdet_threshold(self):
        return self._gdet_threshold_pv.get()

    @gdet_threshold.setter
    def gdet_threshold(self, val):
        self._gdet_threshold_pv.put(val)

    #def HRM(self):
    #    s = '\n' + "Harmonic rejection mirrors:" + '\n'
    #    s += hrm.m1y.status() + 'n'
    #    s += hrm.m2y.status() + 'n'
    #    s += hrm.m1r.status() + 'n'
    #    s += hrm.m2r.status() + 'n'
    #    return s

    def takeJungfrauPedestals(self, record=True, nEvts=1000):
        self._daq.connect()
        recordOrg = self._daq.record
        self._daq.record = record

        srcs = []
        # get the list of Jungfrau in the partition
        for node in self._daq.getPartition()['nodes']:
            if node['record'] and (((node['phy'] & 0xff00) >> 8) == 43):
                srcs.append(node['phy'])
        jfs = [ Jungfrau(self.hutch, src, *self.aliases) for src in srcs ]

        for jf in jfs:
          currMode=jf.get_gainmode()
          print 'current mode: ',jf.gainName(currMode)
        for thisgainmode in self.gainmodes:
          for jf in jfs:
              if isinstance(thisgainmode, basestring):
                  thisgainmode_string = thisgainmode
                  thisgainmode = jf._jfGainMode[thisgainmode]
              else:
                  thisgainmode_string = jf.gainName(thisgainmode)
              print 'switching gainmode to ',thisgainmode_string
              if jf.get_gainmode()!= thisgainmode:
                  jf.set_gainmode(thisgainmode)
                  jf.commit()
                  
                  if jf.get_gainmode() != thisgainmode:
                      print 'waiting for gain to switch from ',jf.gainName(jf.get_gainmode()),' to ', thisgainmode_string
                  while jf.get_gainmode() != thisgainmode:
                        time.sleep(0.5)

          self._daq.configure(events=0)
          print 'take run for gain ',thisgainmode_string
          self._daq.begin(nEvts)
          self._daq.wait()
          self._daq.endrun()
          print 'took run %d for gain %s with %d events'%(self._daq.runnumber(),thisgainmode_string, nEvts)

      #done, set back to normal gain mode.
        for jf in jfs:
          jf.set_gainmode(0)
          jf.commit()
        print 'now call makepeds -J -l -r ',int(self._daq.runnumber())-2

      #reset original record mode & disconnect
        self._daq.record = recordOrg
        self._daq.disconnect()

    def status_Elog(self):
        s =  "Status: "
        s += self.status(mag=False) + '\n'
        s += diff.status() + "\n"
        s += crl2.status() + "\n"
        #s += self.HRM() + "\n"
        s += ipm2.status() + "\n"
        s += ipm5.status() + "\n"
        s += slits(None,None,fast=0, elog =1) + "\n" 
        s += "Fee att:" + "\n"
        s += feeatt.status() + "\n"
        s += "XCS att:" + "\n"
        s += xcsatt.status() + "\n"
        s += "Magnet Pulse:" + "\n"
        s += self.mag.status() + "\n"
        return s

    def status(self, mag=True):
        txt = "** %s Status **\n\t%10s\t%10s\t%10s\n" % (self.expname, "Motor","User","Dial")
        keys = self.motors.keys()
        keys.sort()
        for key in keys:
            m = self.motors[key]
            txt += "\t%10s\t%+10.4f\t%+10.4f\n" % (key,m.wm(),m.wm_dial())
        if mag:
            txt += self.mag.status() + "\n"
        return txt

    def Elog(self,comment=""):
        if (comment != ""): comment += "\n"
        pypsElog.submit(comment+self.status_Elog())

    def _prepNonMagShots(self, nshots):
        self._pp.prepare_burst(nshots, burstMode=True)

    def _prepSpacedNonMagShots(self, nshots_per_burst, spacing):
        nshots = 1
        burstDelay = spacing - 2
        self._pp.prepare_burst(nshots, Nbursts=nshots_per_burst, delay=burstDelay, burstMode=True)

    def _takeNonMagShots(self):
        self._pp.get_burst()

    def _prepMagShot(self, isfire, delay=1):
        self._pp.flipflop()
        self._pp._set_Nbursts(1)
        seqstep = 0
        self._seq.setstep(seqstep,self._pp._codes['pp'],delay,fiducial=0,burst=3,comment='PulsePicker');seqstep+=1
        self._seq.setstep(seqstep,self._pp._codes['drop'],0,fiducial=0,comment='OffEvent');seqstep+=1
        if isfire:
            self._seq.setstep(seqstep,self.mag.eventcode,2,fiducial=0,comment='MagnetPulse');seqstep+=1
            self._seq.setstep(seqstep,self._pp._codes['daq'],0,fiducial=0,comment='OnEvent');seqstep+=1
        else:
            self._seq.setstep(seqstep,self._pp._codes['daq'],2,fiducial=0,comment='OnEvent');seqstep+=1
        self._seq.setnsteps(seqstep)
        self._seq.update()

    def _takeMagShot(self):
        self._pp.get_burst()

    def takeEmptyShots(self, nshots, shotspacing, use_daq=False, record=None):
        calibcontrols=[
            ('nshots', nshots),
            ('shotspacing', shotspacing),
        ]

        if shotspacing > 0:
            self._prepSpacedNonMagShots(nshots, shotspacing)
        else:
            self._prepNonMagShots(nshots)

        # configure daq if being used
        if use_daq:
            self._daq.record = record
            self._daq.configure(controls=calibcontrols,events=0)

        try:
            if use_daq:
                self._daq.begin(events=nshots,controls=calibcontrols)
            self._pp.get_burst()
            self._seq.wait()
            if use_daq:
                self._daq.wait()
        except KeyboardInterrupt:
            self._pp.stop_burst()
            # stop the daq
            if use_daq:
                self._daq.stop()
        finally:
            if use_daq:
                # revert daq record setting to gui control and disconnect
                self._daq.record = None
                self._daq.disconnect()

    def takeMagnetShot(self, nemptyshots, emptyshotspacing=0, isfire=False, record=None):
        calibcontrols=[
            ('mag_isfire', isfire),
            ('mag_trig_delay', self.mag.delay),
            ('mag_trig_width', self.mag.width),
            ('mag_trig_eventcode', self.mag.eventcode),
            ('nemptyshots', nemptyshots),
            ('emptyshotspacing', emptyshotspacing),
        ]

        # check the machine burst rate and set to Full rate if not
        self.check_burst_rate()
        # disable BYKIK before taking shots
        self.bykik_disable()
      
        # check if emptyshotspacing is valid
        if 0 < emptyshotspacing < self._min_empty_delay:
            raise ValueError("When using spacing between empty shots it must be >= %d"%self._min_empty_delay)

        spacer = "*********************************"
        printnow("\n%s\n* Preparing to take magnet shot *\n%s\n"%(spacer, spacer))
        if emptyshotspacing > 0:
            mag_status  = "Taking %d shots, with a spacing between each of %d beam pulses, before firing the magnet\n"%(nemptyshots, emptyshotspacing)
        else:
            mag_status  = "Taking %d shots before firing the magnet\n"%nemptyshots
        mag_status += "Magnet pulse eventcode: %d\n"%self.mag.eventcode
        mag_status += "Magnet pulse trigger delay: %f\n"%self.mag.delay
        mag_status += "Magnet pulse trigger width: %f\n"%self.mag.width
        mag_status += "Magnet to be fired: %s\n"%isfire
        printnow(mag_status)

        try:
            self._daq.record = record
            self._daq.configure(controls=calibcontrols,events=0)

            # Pre empty shots
            if nemptyshots > 0:
                printnow("\nPreparing sequencer for pre-firing, non-magnet shots")
                if emptyshotspacing > 0:
                    self._prepSpacedNonMagShots(nemptyshots, emptyshotspacing)
                else:
                    self._prepNonMagShots(nemptyshots)
                self._daq.begin(events=nemptyshots,controls=calibcontrols)
                printnow("\nTaking %d pre-firing, non-magnet shots\n"%nemptyshots)
                # pause after changing pulse picker mode
                time.sleep(self.pause_time)
                self._takeNonMagShots()
                self._seq.wait()
                self._daq.wait()
            else:
                printnow("\nSkipping prefiring, non-magnet shots\n")

            # pause after empty shots
            time.sleep(self.pause_time)

            # Fire the magnet sequence based on isfire flag
            if isfire:
                printnow("Start magnet firing sequence\n")
            else:
                printnow("Start magnet test 'firing' sequence\n")

            printnow("\nPreparing sequencer for magnet shot")
            if emptyshotspacing > 0:
                self._prepMagShot(isfire, emptyshotspacing)
            else:
                self._prepMagShot(isfire)

            # pause after changing pulse picker mode
            time.sleep(self.pause_time)

            # checking the gdets
            num_tries = 0
            gdet_good = False
            while num_tries < self.gdet_mag_retry:
                gdet_241, gdet242 = self.gdet.energy_24_avg(self.gdet_avg_count)
                if gdet_241 < self.gdet_threshold or gdet242 < self.gdet_threshold:
                    printnow("\nNot firing magnet due to low beam current (gdet 241, 242): %.3f mJ, %.3f mJ\n"%(gdet_241, gdet242))
                    backoff_time = 2 ** num_tries
                    printnow("Sleeping for %d seconds...\n"%backoff_time)
                    time.sleep(backoff_time)
                    num_tries+=1
                else:
                    # gdet is good - fire!
                    gdet_good = True
                    printnow("\nGas detector looks good (gdet 241, 242): %.3f mJ, %.3f mJ\n"%(gdet_241, gdet242))
                    break

            if not gdet_good:
                printnow("Max number of gas detector checks (%d) exceeded! - Abort shot attempt.\n"%self.gdet_mag_retry)
                return False

            # take the magnet shot
            self._daq.begin(events=1,controls=calibcontrols)
            printnow("\nTaking magnet shot\n")
            self._takeMagShot()
            self._seq.wait()
            self._daq.wait()

            # pause after magnet shots
            time.sleep(self.pause_time)

            # Post empty shots
            if nemptyshots > 0:
                printnow("\nPreparing sequencer for post-firing, non-magnet shots")
                if emptyshotspacing > 0:
                    self._prepSpacedNonMagShots(nemptyshots, emptyshotspacing)
                else:
                    self._prepNonMagShots(nemptyshots)
                self._daq.begin(events=nemptyshots,controls=calibcontrols)
                printnow("\nTaking %d post-firing, non-magnet shots\n"%nemptyshots)
                # pause after changing pulse picker mode
                time.sleep(self.pause_time)
                self._takeNonMagShots()
                self._seq.wait()
                self._daq.wait()
            else:
                printnow("\nSkipping post-firing, non-magnet shots\n")
            
            # shot success
            return True
        except KeyboardInterrupt:
            # stop the sequencer
            self._seq.stop()
            # stop the daq
            self._daq.stop()
            # shot killed
            return False
        finally:
            # disconnect from the daq
            self._daq.record = None
            self._daq.disconnect()
            # enable BYKIK after taking shots
            self.bykik_enable()

    def takeMagnetShotMulti(self, nemptyshots, emptyshotspacing=0, isfire=False, record=None, ignore_ready=False):
        """
        Takes magnet shots in a continous fashion waiting for a ready signal from the magnet controller
        """
        latch = False
        nmagshots = 0
        shotgood = True
        spacer = '##############################'
        try:
            while shotgood:
                if not latch and (self.ready_sig > self.ttl_high or ignore_ready):
                    # check if the beam is good
                    gdet_241, gdet242 = self.gdet.energy_24_avg(self.gdet_avg_count)
                    if gdet_241 < self.gdet_threshold or gdet242 < self.gdet_threshold:
                        printnow("\nNot firing magnet due to low beam current (gdet 241, 242): %.3f mJ, %.3f mJ\n"%(gdet_241, gdet242))
                        backoff_time = 1
                        printnow("Sleeping for %d second...\n"%backoff_time)
                        time.sleep(backoff_time)
                        continue
                    # if the beam is good start the sequence
                    latch = True
                    printnow("\n%s\nStarting shot %d\n%s\n"%(spacer,nmagshots,spacer))
                    start_time = time.time()
                    shotgood = self.takeMagnetShot(nemptyshots, emptyshotspacing, isfire, record)
                    stop_time = time.time()
                    printnow("\n%s\nCompleted shot %d in %.2f s\n%s\n"%(spacer,nmagshots,(stop_time-start_time),spacer))
                    nmagshots += 1
                if latch and (self.ready_sig < self.ttl_low or ignore_ready):
                    latch = False
                time.sleep(0.25)
        except KeyboardInterrupt:
            printnow('\nExiting...\n')
        finally:
            printnow('Took %d total magnet shots\n'%nmagshots)

