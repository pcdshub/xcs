import logging
import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from hutch_python.utils import safe_load
from pcdsdevices.epics_motor import SmarAct, EpicsMotorInterface
from pcdsdevices.interface import BaseInterface


logger = logging.getLogger(__name__)

#all commented out for FeeComm(Test)

from pcdsdevices import analog_signals
with safe_load('Split and Delay'):
   from hxrsnd.sndsystem import SplitAndDelay
   from xcs.db import daq, RE
   snd = SplitAndDelay('XCS:SND', name='snd', daq=daq, RE=RE)
 
with safe_load('analog_out'):
    aio = analog_signals.Acromag(name = 'xcs_aio', prefix = 'XCS:USR')

def motor_status(motors):
    """
    print motor postion and preset name
    Ex)
    motors={'samx': x.sam_x,'samy': x.sam_y,'samz':x.sam_z,'samth': x.sam_th}
    motor_status(motors)
    samx: 1.000, s1
    samy: 1.000, s1
    samz: 1.000, s2
    samth: 1.000, Unknown
    """
    header = f"{'Motor': <10} {'Position': <20} {'Preset Position': <15}"
    print(header)
    print("-" * len(header))
    for name, motor in motors.items():
        try:
            position = motor.wm()
            preset_name = motor.presets.state()
            print(f"{name:<10}: {position:<20},    {preset_name:<15}")
        except Exception as e:
            print(f"{name:<10}: Fail to read the position: {e}")

with safe_load('DCCM'):
   from pcdsdevices.device_types import DCCM
   dccm = DCCM(name='DCCM')

# DCCM macro #
with safe_load('SP1l0'):
    from pcdsdevices.device_types import BeckhoffAxis
    dccm_th1 = BeckhoffAxis('SP1L0:DCCM:MMS:TH1',name='dccmth1')
    dccm_th2 = BeckhoffAxis('SP1L0:DCCM:MMS:TH2',name='dccmth2')

def dccm_time_delay(Energy=9500,gap=9.899):
    """
    calibrate time difference between pink vs dccm
    by sanghoon
    """
    d_space = 3.13560114 
    c = 0.299792458 #mm/ps
    bragg_angle = np.rad2deg(np.arcsin(12398.419/Energy/(2*d_space)))
    path_diff = 2*gap*(1-np.cos(np.radians(2*bragg_angle)))/np.sin(np.radians(bragg_angle))
    time_delay = path_diff/c
    print('Energy: {:.1f}eV will delay {:.1f}ps'.format(Energy,time_delay))



#def si111energy(theta=8.5):
#    d_space = 3.13560114
#    energy = 12398.419/(2*d_space*np.sin(np.deg2rad(theta)))
#    return energy
    
#def si111bragg(energy=9800):
#    d_space = 3.13560114
#    bragg_angle = np.rad2deg(np.arcsin(12398.419/energy/(2*d_space)))
#    return bragg_angle

#def dccm_sanghoon():
#    print('th1(deg): {:.4f}'.format(dccm_th1.wm()))
#    print('th2(deg): {:.4f}'.format(dccm_th1.wm()))
#    energy=si111energy(dccm_th1.wm())
#    print('Energy(eV): {:.2f}'.format(energy))
#    return energy

#def dccm_energy(energy):
#    """
#    move the dccm th1 and th2 to energy (eV)
#    """
#    bragg_angle=si111bragg(energy)
#    dccm_th1.mv(bragg_angle)
#    dccm_th2.umv(bragg_angle)

#from epics import caget,caput

#def dccm_e_vernier(energy):
#    """     move the dccm th1 and th2 to energy with veriner eV """ 
#    dccm_energy(energy)    
#    caput('XCS:USER:MCC:EPHOT:SET1',energy)

from epics import caget,caput
def dccm_yag3m_image(filename='test',nshot=300):
    fdir='/reg/d/iocData/ioc-xrt-gige-yag3m/'    
    filename=filename
    if os.path.exists(fdir+filename+'.h5'):
        answer = input (f"'{filename}' exist, overwrite (Y/N): ").strip().lower()
        if answer == 'y':
            caput('XCS:GIGE:YAG3M:HDF51:FilePath',fdir)
            caput('XCS:GIGE:YAG3M:HDF51:FileName',filename)
            caput('XCS:GIGE:YAG3M:HDF51:NumCapture',nshot)
            caput('XCS:GIGE:YAG3M:HDF51:Capture',1)
            print('collecting yag3m image ' , nshot , 'shots')
            sleep(nshot/5+5)
            image_saturation_check(fdir,filename,nshot)
        else: 
            print('try to use new file name')
    else:           
        caput('XCS:GIGE:YAG3M:HDF51:FilePath',fdir)
        caput('XCS:GIGE:YAG3M:HDF51:FileName',filename)
        caput('XCS:GIGE:YAG3M:HDF51:NumCapture',nshot)
        caput('XCS:GIGE:YAG3M:HDF51:Capture',1)
        print('collecting yag3m image ' , nshot , 'shots')
        sleep(nshot/5+5)
        image_saturation_check(fdir,filename,nshot)


import numpy as np
import h5py 
def image_saturation_check(fdir,filename,nshot):
    data=h5py.File(fdir+filename+'.h5','r')
    imgs=data['entry/data/data']
    saturation_level = 4000
    background_level = 100
    nimg=nshot
    saturation_img=np.zeros(nimg)
    for i in range(nimg):
        saturation_img[i]=(np.sum(imgs[i,:,:] >= saturation_level)/np.sum(imgs[i,:,:] >= background_level))*100
    saturation_rate= (np.sum(saturation_img >=5) / nimg)*100
    if  saturation_rate>10:
        print('image is satured, please put attenuator')
    else :
        plt.figure()
        plt.imshow(np.mean(imgs,axis=0))
        print('collected image')

 
def continuous_dccmscan(energies, pointTime=1, move_vernier=False, bidirectional=False):
    initial_energy=dccm.energy.wm()
    try:
        for E in energies:
            if move_vernier:
                dccm.energy_with_vernier(E)
                print(f'Moving DCCM with vernier to {E}')
            else:
                dccm.energy(E)
                print(f'Moving DCCM to {E}')
            time.sleep(pointTime)
        if bidirectional:
            for E in energies[::-1]:
                if move_vernier:
                    dccm.energy_with_vernier(E)
                    print(f'Moving DCCM with vernier to {E}')
                else:
                    dccm.energy(E)
                    print(f'Moving DCCM to {E}')
                time.sleep(pointTime)

    except KeyboardInterrupt:
        print(f'Scan end signal received. Returning ccm to energy before scan: {initial_energy}')
        dccm_e_vernier(initial_energy)
        print(f'Moving ccm.E_Vernier to {initial_energy}')

    finally:
        if move_vernier:
            dccm.energy_with_vernier(initial_energy)
            print(f'Moving back initial energy to {initial_energy}')
        else:
            dccm.energy(initial_energy)
            print(f'Moving back initial energy to {initial_energy}')
        time.sleep(pointTime)

def run_dccmscan(energies, record=True,  pointTime=1,  move_vernier=True,bidirectional=False,**kwargs):
        logger.info("Starting DAQ run, -> record=%s", record)
        daq.configure()
        try:
            #start DAQ, then start scanning
            daq.begin_infinite(record=record) #note we do not specify # of events, so it records until we stop
            runnum = daq._control.runnumber()
            time.sleep(1) # give DAQ a second
            continuous_dccmscan(energies, pointTime=pointTime, move_vernier=move_vernier,bidirectional=bidirectional)
        except KeyboardInterrupt:
            print('Interrupt signal received. Stopping run and DAQ')
        finally: 
            daq.end_run()
            logger.info("Run complete!")
            #daq.disconnect()



## Low-T remote control


def lowt_compressor_on():
    answer = input(f"Water colling is on(Y/N): ").strip().lower()
    if answer == 'y':
        aio.ao1_0.set(9)
    else:
        print("try again after turn on water cooling")

def lowt_compressor_off():
    aio.ao1_0.set(0)
    print("Compressor off")

def lowt_inlet_on():
    aio.ao1_1.set(9)
    print("inlet open")

def lowt_inlet_off():
    aio.ao1_1.set(0)
    print("inlet close")

def lowt_outlet_on():
    aio.ao1_2.set(9)
    print("outlet open")

def lowt_outlet_off():
    aio.ao1_2.set(0)
    print("outlet close")



# Split delay macro #
def show_cc():
    aio.ao1_5.set(0)
    aio.ao1_4.set(5)
    print("SND CC only")

def show_delay():
    aio.ao1_5.set(5)
    aio.ao1_4.set(0)
    print("SND Delay only")

def show_both():
    aio.ao1_5.set(5)
    aio.ao1_4.set(5)
    print("SND Both open")

def show_neither():
    aio.ao1_5.set(0)
    aio.ao1_4.set(0)
    print("SND Both block")

def snd_cc_out():
    snd.t2.x.mv_out()
    snd.t3.x.umv_out()
    print("SND CC crystals is OUT")

def snd_cc_in():
    snd.t2.x.mv_in()
    snd.t3.x.umv_in()
    print("SND CC crystals is IN")

def snd_dd_out():
    print("SND t1.y1 position:{:.2f}".format(snd.t1.y1.wm()))
    print("SND t4.y1 position:{:.2f}".format(snd.t4.y1.wm()))      
    snd.t1.y1.mv_out()
    snd.t4.y1.mv_out()
    print("NOW. SND Delay crystals is OUT. t1.y1 and y4.y1 move OUT")

def snd_dd_in():
    snd.t1.y1.mv_in()
    snd.t4.y1.mv_in()
    print("NOW. SND Delay crystals is IN. t1.y1 and y4.y1 move IN")


def snd_clear():
    """
    Clear the t1 and t4, x, tth, L status to "GO"    
    """
    os.system('caput XCS:SND:T1:X.SPMG 3')
    os.system('caput XCS:SND:T1:TTH.SPMG 3')
    os.system('caput XCS:SND:T1:L.SPMG 3')
    os.system('caput XCS:SND:T4:X.SPMG 3')
    os.system('caput XCS:SND:T4:TTH.SPMG 3')
    os.system('caput XCS:SND:T4:L.SPMG 3')

def snd_enable_all():
    """
    Clear the t1 and t4, x, tth, L status to "GO"    
    """
    os.system('caput XCS:SND:T1:X.CNEN 1')
    os.system('caput XCS:SND:T1:TTH.CNEN 1')
    os.system('caput XCS:SND:T1:L.CNEN 1')
    os.system('caput XCS:SND:T1:TH1.CNEN 1')
    os.system('caput XCS:SND:T1:TH2.CNEN 1')

    os.system('caput XCS:SND:T4:X.CNEN 1')
    os.system('caput XCS:SND:T4:TTH.CNEN 1')
    os.system('caput XCS:SND:T4:L.CNEN 1')
    os.system('caput XCS:SND:T4:TH1.CNEN 1')
    os.system('caput XCS:SND:T4:TH2.CNEN 1')

    os.system('caput XCS:SND:T2:X.CNEN 1')
    os.system('caput XCS:SND:T2:TH.CNEN 1')
    os.system('caput XCS:SND:T3:X.CNEN 1')
    os.system('caput XCS:SND:T3:TH.CNEN 1')

def snd_home():
    print('homing the snd motors')
    user_input = input("Do you want to home the diodes(DI, DCI, DCO, DO, DCC, DD)? (y/n): ")
    if user_input.lower() in["yes","y"]:
        print("homing")
        snd.di.x.home('forward')
        snd.dci.x.home('forward')
        snd.dco.x.home('forward')
        snd.do.x.home('forward')
        snd.dcc.x.home('forward')
        snd.dd.x.home('forward')
    elif user_input.lower() in["no","n"]:
        print("skipping")

    user_input = input("Do you want to home t1.th1, t1.th2, t4.th1, t4.th2? (y/n): ")
    if user_input.lower() in["yes","y"]:
        print("homing")
        snd.t1.th1.home('forward')
        snd.t4.th1.home('forward')
        snd.t1.th2.home('forward')
        snd.t4.th2.home('forward')
    elif user_input.lower() in["no","n"]:
        print("skipping")

    user_input = input("Do you want to home t2.x, t2.th,t3.x, t3.th? (y/n): ")
    print('please make sure the CC crystal is ok to home')
    if user_input.lower() in["yes","y"]:
        print("homing")
        snd.t2.x.home('forward')
        snd.t3.x.home('forward')
        snd.t2.th.home('forward')
        snd.t3.th.home('forward')
    elif user_input.lower() in["no","n"]:
        print("skipping")

    user_input = input("Do you want to home t1.x, t1.tth, t4.x, t4.tth? (y/n): ")
    if user_input.lower() in["yes","y"]:
        print("homing")
        snd.t1.L.umv(250)
        snd.t4.L.umv(250)
        snd.t1.tth.home('reverse')
        snd.t4.tth.home('forward')
        snd.t1.x.home('reverse')
        snd.t4.x.home('forward')
        snd.t1.x.umv(0)
        snd.t4.x.umv(0)
    elif user_input.lower() in["no","n"]:
        print("skipping")


    return True

def snd_park():
    snd.t1.L.mv(250)
    snd.t4.L.umv(250)

    snd.di.x.mv(-90,wait = False)
    snd.dd.x.mv(-270,wait = False)
    snd.do.x.mv(-80,wait = False)
    snd.dci.x.mv(70,wait = False)
    snd.dco.x.mv(70,wait = False)
    snd.dcc.x.mv(110,wait = False)

    snd.t1.tth.mv(0,wait = True)
    snd.t4.tth.umv(0)

    snd.t2.x.mv(70,wait = False)

    snd.t1.x.mv(85)
    snd.t4.x.mv(85)

    snd.t3.x.mv(70)
    return True

def snd_branch_ratio_calibration(nshots=240,do_ch=9):
    """SND CC and Delay line branch ration calbiration with DCO or IPM5.
      CC use ch 9(after CC line), DD use ch 15(after 3rd crystal),
      DCO is ch 6 IPM5 is ch 9"""
    sndall=EpicsSignal('XCS:TT:01:SNDDIO.VALA')
    user_input = input("Calibration with IPM5(y) or DO(n): ")
    if user_input.lower() in["yes","y"]:
        do_ch = 9
    else:
        do_ch = 6

    ipm5_vals=np.zeros(nshots)
    dd_vals=np.zeros(nshots) #ch15
    do_vals=np.zeros(nshots) #ch9
    cc_vals=np.zeros(nshots) #ch14
    #Ch8, CC (Ch9), Ch10, Ch11, Ch12, Ch13, Ch14, Delay (Ch15), IPM4 Sum, IPM5 Sum.        
    print('Collect {} shots'.format(nshots))
    show_cc();sleep(0.5)
    for i in range(nshots):
        snddata=sndall.get()
        dd_vals[i]=snddata[7,]
        cc_vals[i]=snddata[1,]
        do_vals[i]=snddata[do_ch,]
        sleep(0.005)
    initial_guess = [30,1,1]
    x=do_vals;y=cc_vals;
    popt, _ = curve_fit(poly1, x, y, p0=initial_guess)
    slop1,xoffset1,yoffset1 = popt
#    do_ref=np.nanmean(do_vals)
#    cc_ref=np.nanmean(cc_vals)
    coff_cc=slop1
    print('coefficient CC : {:.2f}'.format(coff_cc))
    plt.figure()
    plt.subplot(2,2,1)
    plt.plot(do_vals,cc_vals,'.')
    plt.plot(x, poly1(x, *popt), linestyle='--', color='r');plt.tight_layout()
    plt.grid();
    plt.xlabel('DO signal');
    plt.ylabel('CC signal'); plt.title("CC only")
    show_delay();sleep(0.5)
    dd_vals=np.zeros(nshots) #ch15
    do_vals=np.zeros(nshots) #ch9
    cc_vals=np.zeros(nshots) #ch14
    for i in range(nshots):
        snddata=sndall.get()
        dd_vals[i]=snddata[7,]
        cc_vals[i]=snddata[1,]
        do_vals[i]=snddata[do_ch,]
        sleep(0.005)
    initial_guess = [30,1,1]
    x=do_vals;y=dd_vals;
    popt, _ = curve_fit(poly1, x, y, p0=initial_guess)
    slop2,xoffset2,yoffset2 = popt
#    do_ref=np.nanmean(do_vals)
#    dd_ref=np.nanmean(dd_vals)
#    coff_dd=dd_ref/do_ref
    coff_dd=slop2
    print('coefficient DD : {:.2f}'.format(coff_dd))
    plt.subplot(2,2,2)
    plt.plot(do_vals,dd_vals,'.')
    plt.plot(x, poly1(x, *popt), linestyle='--', color='r');plt.tight_layout()
    plt.grid();
    plt.xlabel('DO signal');
    plt.ylabel('DD signal'); plt.title("DD only")
    show_both()
    dd_vals=np.zeros(nshots) #ch15
    do_vals=np.zeros(nshots) #ch9
    cc_vals=np.zeros(nshots) #ch14
    for i in range(nshots):
        snddata=sndall.get()
        dd_vals[i]=(snddata[7,]+xoffset1)*coff_dd+yoffset1
        cc_vals[i]=(snddata[1,]+xoffset2)*coff_cc+yoffset2
        do_vals[i]=snddata[do_ch,]
        sleep(0.005)
    ratios = 1+(dd_vals-cc_vals)/do_vals
    ratio = np.nanmean(ratios)
    print('Ratio [1+(Delay-ChannelCut)/Sum]: {:.2f}'.format(ratio))
    plt.subplot(2,2,3)
    plt.plot(cc_vals,dd_vals,'.')
    plt.grid()
    plt.xlabel('CC signal')
    plt.ylabel('DD signal'); plt.title("Both correlation")
    plt.subplot(2,2,4)
    plt.plot(do_vals,ratios,'.')
    plt.grid()
    plt.xlabel('Sum signal');plt.title("Ratios")
    plt.ylabel('Ratios')
    plt.tight_layout()
    plt.show()
    return

# Gaussian function for fitting
def gaussian(x, center, sigma, amplitude,yoffset):
    return amplitude * np.exp(-((x - center) ** 2) / (2 * sigma ** 2))+yoffset
# Poly1 function for fitting
def poly1(x,slop,xoffset,yoffset):
    return slop*(x+xoffset)+yoffset

def snd_cc_rocking(nshots=60,scanrange=3e-3,nstep=21):
    " snd delay line rocking, first crystal pink range 1e-2, mono range 3e-3"
    print('CC line rocking check')
    user_input = input("Start t2.th(y): ")
    scanstep=scanrange/((nstep-1)/2)
    plt.figure()
    #Ch8(CC), Ch9(DCO), Ch10, Ch11(DD after t1.xtal1), Ch12(DD after t1.xtal2), Ch13, Ch14(DO), CH15(Delay), IPM4 Sum, IPM5 Sum.        
    if user_input.lower() in["yes","y"]:
        th1=np.zeros(nstep);
        th1_data=np.zeros(nstep);
        snd.t2.th.umvr(-1*scanrange)
        for i in range(nstep):
            th1[i]=snd.t2.th.wm()
            th1_data[i]=get_snd_signal(nshots,I0=8,II=0)
            snd.t2.th.umvr(scanstep)
        snd.t2.th.umvr(-1*scanrange)
        x=th1;y=th1_data;
        initial_guess = [np.mean(x), np.std(x), np.max(y),np.min(y)]
        popt, _ = curve_fit(gaussian, x, y, p0=initial_guess)
        center, sigma, amplitude,yoffset = popt

        plt.subplot(1,2,1);
        plt.plot(x,y,'.');plt.xlabel('t2.th');plt.grid()
        plt.plot(x, gaussian(x, *popt), linestyle='--', color='r');plt.tight_layout()
        plt.title('Center : {:.5f}'.format(center)+' FWHM: {:.5f}'.format(2.3548*sigma))
        plt.draw()
        print('t2.th center:{:.6f}'.format(center))
        user_input = input("Do you want to move center(y): ")
        if user_input.lower() in["yes","y"]: snd.t2.th.umv(center)
    user_input = input("Start t3.th(y): ")
    if user_input.lower() in["yes","y"]:
        th2=np.zeros(nstep);
        th2_data=np.zeros(nstep);
        snd.t3.th.umvr(-1*scanrange)
        for i in range(nstep):
            th2[i]=snd.t3.th.wm()
            th2_data[i]=get_snd_signal(nshots,I0=8,II=1)
            snd.t3.th.umvr(scanstep)
        snd.t3.th.umvr(-1*scanrange)
        x=th2;y=th2_data;
        initial_guess = [np.mean(x), np.std(x), np.max(y),np.min(y)]
        popt, _ = curve_fit(gaussian, x, y, p0=initial_guess)
        center, sigma, amplitude,yoffset = popt

        plt.subplot(1,2,2);
        plt.plot(x,y,'.');plt.xlabel('t3.th');plt.grid()
        plt.plot(x, gaussian(x, *popt), linestyle='--', color='r');plt.tight_layout()
        plt.title('Center : {:.5f}'.format(center)+' FWHM: {:.5f}'.format(2.3548*sigma))
        plt.draw()
        print('t3.th center:{:.6f}'.format(center))
        user_input = input("Do you want to move center(y): ")
        if user_input.lower() in["yes","y"]: snd.t3.th.umv(center)


def snd_delay_rocking(nshots=60,scanrange=3e-3,nstep=21):
    " snd delay line rocking, first crystal pink range 1e-2, mono range 3e-3"
    print('Delay line rocking check')
    user_input = input("Start t1.th1(y): ")
    scanstep=scanrange/((nstep-1)/2)
    plt.figure()
    #Ch8(CC), Ch9(DCO), Ch10, Ch11(DD after t1.xtal1), Ch12(DD after t1.xtal2), Ch13, Ch14(DO), CH15(Delay), IPM4 Sum, IPM5 Sum.        
    if user_input.lower() in["yes","y"]:
        th1=np.zeros(nstep);
        th1_data=np.zeros(nstep);
        snd.t1.th1.umvr(-1*scanrange)
        for i in range(nstep):
            th1[i]=snd.t1.th1.wm()
            th1_data[i]=get_snd_signal(nshots,I0=8,II=3)
            snd.t1.th1.umvr(scanstep)
        snd.t1.th1.umvr(-1*scanrange)
        x=th1;y=th1_data;
        initial_guess = [np.mean(x), np.std(x), np.max(y),np.min(y)]
        popt, _ = curve_fit(gaussian, x, y, p0=initial_guess)
        center, sigma, amplitude,yoffset = popt

        plt.subplot(2,2,1);
        plt.plot(x,y,'.');plt.xlabel('t1.th1');plt.grid()
        plt.plot(x, gaussian(x, *popt), linestyle='--', color='r');plt.tight_layout()
        plt.title('Center : {:.5f}'.format(center)+' FWHM: {:.5f}'.format(2.3548*sigma))
        plt.draw()
        print('t1.th2 center:{:.6f}'.format(center))
        user_input = input("Do you want to move center(y): ")
        if user_input.lower() in["yes","y"]: snd.t1.th1.umv(center)
    user_input = input("Start t1.th2(y): ")
    if user_input.lower() in["yes","y"]:
        th2=np.zeros(nstep);
        th2_data=np.zeros(nstep);
        snd.t1.th2.umvr(-1*scanrange)
        for i in range(nstep):
            th2[i]=snd.t1.th2.wm()
            th2_data[i]=get_snd_signal(nshots,I0=3,II=4)
            snd.t1.th2.umvr(scanstep)
        snd.t1.th2.umvr(-1*scanrange)
        x=th2;y=th2_data;
        initial_guess = [np.mean(x), np.std(x), np.max(y),np.min(y)]
        popt, _ = curve_fit(gaussian, x, y, p0=initial_guess)
        center, sigma, amplitude,yoffset = popt

        plt.subplot(2,2,2);
        plt.plot(x,y,'.');plt.xlabel('t1.th2');plt.grid()
        plt.plot(x, gaussian(x, *popt), linestyle='--', color='r');plt.tight_layout()
        plt.title('Center : {:.5f}'.format(center)+' FWHM: {:.5f}'.format(2.3548*sigma))
        plt.draw()
        print('t1.th2 center:{:.6f}'.format(center))
        user_input = input("Do you want to move center(y): ")
        if user_input.lower() in["yes","y"]: snd.t1.th2.umv(center)

    user_input = input("Start t4.th2(y): ")
    if user_input.lower() in["yes","y"]:

        th3=np.zeros(nstep);
        th3_data=np.zeros(nstep);
        snd.t4.th2.umvr(-1*scanrange)
        for i in range(nstep):
            th3[i]=snd.t4.th2.wm()
            th3_data[i]=get_snd_signal(nshots,I0=4,II=7)
            snd.t4.th2.umvr(scanstep)
        snd.t4.th2.umvr(-1*scanrange)
        x=th3;y=th3_data;
        initial_guess = [np.mean(x), np.std(x), np.max(y),np.min(y)]
        popt, _ = curve_fit(gaussian, x, y, p0=initial_guess)
        center, sigma, amplitude,yoffset = popt

        plt.subplot(2,2,3);
        plt.plot(x,y,'.');plt.xlabel('th4.th2');plt.grid()
        plt.plot(x, gaussian(x, *popt), linestyle='--', color='r');plt.tight_layout()
        plt.title('Center : {:.5f}'.format(center)+' FWHM: {:.5f}'.format(2.3548*sigma))
        plt.draw()
        print('t4.th2 center:{:.6f}'.format(center))
        user_input = input("Do you want to move center(y): ")
        if user_input.lower() in["yes","y"]: snd.t4.th2.umv(center)

    user_input = input("Start t4.th1(y): ")

    if user_input.lower() in["yes","y"]:
        th4=np.zeros(nstep);
        th4_data=np.zeros(nstep);
        snd.t4.th1.umvr(-1*scanrange)
        user_input = input("Normalized by IPM5(y) or DO(n): ")
        if user_input.lower() in["yes","y"]:
            for i in range(nstep):
                th4[i]=snd.t4.th1.wm()
                th4_data[i]=get_snd_signal(nshots,I0=7,II=9)
                snd.t4.th1.umvr(scanstep)
        else:
            for i in range(nstep):
                th4[i]=snd.t4.th1.wm()
                th4_data[i]=get_snd_signal(nshots,I0=7,II=6)
                snd.t4.th1.umvr(scanstep)

        snd.t4.th1.umvr(-1*scanrange)
        x=th4;y=th4_data;
        initial_guess = [np.mean(x), np.std(x), np.max(y),np.min(y)]
        popt, _ = curve_fit(gaussian, x, y, p0=initial_guess)
        center, sigma, amplitude,yoffset = popt

        plt.subplot(2,2,4);
        plt.plot(x,y,'.');plt.xlabel('t4.th1');plt.grid()
        plt.plot(x, gaussian(x, *popt), linestyle='--', color='r');plt.tight_layout()
        plt.title('Center : {:.5f}'.format(center)+' FWHM: {:.5f}'.format(2.3548*sigma))
        plt.draw()
        print('t4.th1 center:{:.6f}'.format(center))
        user_input = input("Do you want to move center(y): ")
        if user_input.lower() in["yes","y"]: snd.t4.th1.umv(center)

    return

def get_snd_signal(nshots=60,I0=8,II=3):
    sndall=EpicsSignal('XCS:TT:01:SNDDIO.VALA')
    #Ch8, CC (Ch9), Ch10, Ch11, Ch12, Ch13, Ch14, Delay (Ch15), IPM4 Sum, IPM5 Sum.        
    I0_vals=np.zeros(nshots)
    II_vals=np.zeros(nshots)
    for i in range(nshots):
        snddata=sndall.get()
        I0_vals[i]=snddata[I0,]
        II_vals[i]=snddata[II,]
        sleep(0.005)
    data=np.nanmean(II_vals)/np.nanmean(I0_vals)
    return data

# mode chang Pink or CCM "

with safe_load('Mode change'):
    class bl():
        def mode_pink():
            print("moving ccm.x to 15")
            ccm.x.umv(15)
            print("moving s3.vo and ipm3 diode to pink")
            s3.vo.umv(0)
            s3.ho.umv(0)
            ipm3.diode.y_motor.umv(0)
            print("moving s4.vo, ipm4 target and diode to pink")
            s4.vo.umv(0)
            s4.ho.umv(0)
            ipm4.diode.y_motor.umv(0)
            ipm4.ty.umv(18.5522)
            print("moving pulse picker and tt_vert to pink")
            pp.y.umv(0)
            tt_vert.umv(0)
            print("moving s5.vo and s6.vo, ipm5 target and diode to pink")
            s5.vo.umv(0)
            s5.ho.umv(0)
            ipm5.diode.y_motor.umv(0)
            ipm5.ty.umv(18.25)
            s6.vo.umv(0)
            print("done moving to pink")

        def mode_ccm():
            print("moving ccm.x to 1")
            ccm.x.umv(0)
            print("moving s3.vo, ipm3 diode to ccm")
            s3.vo.umv(7.7496)
            s3.ho.umv(0.4635)
            ipm3.diode.y_motor.umv(7.5)
            print("moving s4.vo, ipm4 diode and target to ccm")
            s4.vo.umv(7.4347)
            s4.ho.umv(-0.1401)
            ipm4.diode.y_motor.umv(7.5)
            ipm4.ty.umv(26.0547)
            print("moving pulse picker and tt_vert to ccm")
            pp.y.umv(9.5)
            tt_vert.umv(7.5)
            tt_ty.umv(39.3237)
            print("moving s5.vo and s6.vo, ipm5 target and diode to ccm")
            s5.vo.umv(7.1143)
            s5.ho.umv(-1.1227)
            ipm5.diode.y_motor.umv(7.5)
            ipm5.ty.umv(39.4946) #25.75
            s6.vo.umv(7.5)

            print('MR1L3:-30.5 and MR2L3: 93.0 2024-04-29')
            print('pre focusing lens:', crl1.y_motor.wm())
            print('beamline lens:', crl2.y.wm())
            print('\x1b[0;37;41m'+'CRL lens has not moved yet'+'\x1b[0m')
            print('\x1b[0;37;41m'+'ALso need to check lib y'+'\x1b[0m')


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
        lxe = LXE('XCS:LAS:MMN:05', calibration_file=lxe_calib_file, name='lxe')    
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


    las_wp = Newport('XCS:LAS:MMN:05', name='las_wp')
    las_ND_wheel = Newport('XCS:LAS:MMN:04', name='las_opa_wp')
    lens_h = Newport('XCS:USR:MMN:01', name='lens_h')
    lens_v = Newport('XCS:LAS:MMN:06', name='lens_v')
    lens_f = Newport('XCS:LAS:MMN:07', name='lens_f')
    pol_wp = Newport('XCS:USR:MMN:07', name='pol_wp')



    # It's okay to be a little unhappy, no need to whine about it
#    from ophyd.epics_motor import AlarmSeverity
    import logging
#    lxt_fast.tolerated_alarm = AlarmSeverity.MINOR
    logging.getLogger('pint').setLevel(logging.ERROR)

with safe_load('CW Laser'):
    from pcdsdevices.analog_signals import Acromag
    from time import sleep
    class CW_Laser():
        def __init__(self):
            self.signals = Acromag('XCS:USR', name='CW_Laser_Mode')
            self.cw_las = self.signals.ao1_3
        def on(self):
            self.cw_las.put(5)
        def off(self):
            self.cw_las.put(0)
    cw_las = CW_Laser()


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
        sync_limits = (-2e-3, 2e-3)
       
    lxt_ttc = LXTTTC('', name='lxt_ttc')


with safe_load('Delay Scan'):
    from ophyd.device import Device, Component as Cpt
    from ophyd.signal import EpicsSignal
    from .delay_scan import delay_scan, USBEncoder
    lxt_fast_enc = USBEncoder('XCS:USDUSB4:01:CH0',name='lxt_fast_enc')
    
    labmax = EpicsSignal('XCS:LPW:01:DATA_PRI') #laser power meter

with safe_load('Other Useful Actuators'):
    from pcdsdevices.epics_motor import IMS
    from ophyd.signal import EpicsSignal
    tt_ty = IMS('XCS:SB2:MMS:46',name='tt_ty')
    tt_tx = IMS('XCS:SB2:MMS:45',name='tt_tx')
    lib_x = IMS('XCS:SB2:LIB:X',name='lib_x')
    lib_y = IMS('XCS:SB2:LIB:Y',name='lib_y')
    #det_y = IMS('XCS:USR:MMS:38',name='det_y')
    
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
#    det_x = Newport('XCS:USR:MMN:08', name='det_x')
    tt_vert = Newport('XCS:USR:MMN:02', name='tt_vert')
    TT_vert = tt_vert
#    det_z = Newport('XCS:USR:MMN:16', name='det_z')
#    bs_x = Newport('XCS:USR:MMN:03', name='bs_x')
#    JF_x = Newport('XCS:USR:MMN:05', name='JF_x')
#    bs_y = Newport('XCS:USR:MMN:06', name='bs_y')
class cdiff_SmarAct(BaseInterface, Device):
    tab_component_names = True
    #mirr_x = Cpt(SmarAct, ':01:m1', kind='normal')                                                                                                                                                               
    #mirr_y = Cpt(SmarAct, ':01:m2', kind='normal')                                                                                                                                                               
    #mirr_dy = Cpt(SmarAct, ':01:m3', kind='normal')                                                                                                                                                              
    #mirr_dx = Cpt(SmarAct, ':01:m4', kind='normal')                                                                                                                                                              
    #mono_th = Cpt(SmarAct, ':01:m5', kind='normal')                                                                                                                                                              
    #pr_th = Cpt(SmarAct, ':01:m5', kind='normal')                                                                                                                                                                
    #pr_x = Cpt(SmarAct, ':01:m6', kind='normal')                                                                                                                                                                 
    #pr_y = Cpt(SmarAct, ':01:m7', kind='normal')                                                                                                                                                                 
    #las_rot = Cpt(SmarAct, ':01:m10', kind='normal')                                                                                                                                                             
    #lib_mirror_v = Cpt(SmarAct, ':01:m5', kind='normal')                                                                                                                                                         
    #pr_h = Cpt(SmarAct, ':01:m7', kind='normal')                                                                                                                                                                     #pr_th = Cpt(SmarAct, ':01:m9', kind='normal')                                                                                                                                                                
    #pr_v = Cpt(SmarAct, ':01:m8', kind='normal')                                                                                                                                                                 
    #mono1_th = Cpt(SmarAct, ':01:m6', kind='normal')                                                                                                                                                             
    #crl_y = Cpt(SmarAct, ':01:m1', kind='normal')                                                                                                                                                                
    #lib_mirror_h = Cpt(SmarAct, ':01:m2', kind='normal')                                                                                                                                                          
    usam_sh = Cpt(SmarAct, ':01:m7', kind='normal')
    usam_z = Cpt(SmarAct, ':01:m2', kind='normal')
    usam_phi = Cpt(SmarAct, ':01:m3', kind='normal')
    usam_x = Cpt(SmarAct, ':01:m1', kind='normal')

class cdiff():#lib unit                                                                                                                                                                                            
    tab_component_names = True
    with safe_load('cdiff SmarAct'):
        lib = cdiff_SmarAct('XCS:MCS2', name='cdiff_smaract')
usam_phi = cdiff.lib.usam_phi
usam_sh = cdiff.lib.usam_sh
usam_x = cdiff.lib.usam_x
usam_z = cdiff.lib.usam_z

"""
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
"""
with safe_load('Liquid Jet'):
    from pcdsdevices.jet import BeckhoffJet
    ljh = BeckhoffJet('XCS:LJH', name='ljh')

"""
with safe_load('Gen1 von Hamos'):
    from pcdsdevices.spectrometer import Gen1VonHamos4Crystal
    vh = Gen1VonHamos4Crystal('MFX:VHS:MMB', name='Gen1 Von Hamos Spectrometer')

    class VonHamos_Spec(Device):
       cr1_tilt = Cpt(BeckhoffAxis, ':10', name='cr1_tilt')
       cr2_tilt = Cpt(BeckhoffAxis, ':11', name='cr2_tilt')
       cr3_tilt = Cpt(BeckhoffAxis, ':12', name='cr3_tilt')
       cr4_tilt = Cpt(BeckhoffAxis, ':13', name='cr4_tilt')
       cr1_move = Cpt(BeckhoffAxis, ':02', name='cr1_move')
       cr2_move = Cpt(BeckhoffAxis, ':03', name='cr2_move')
       cr3_move = Cpt(BeckhoffAxis, ':04', name='cr3_move')
       cr4_move = Cpt(BeckhoffAxis, ':05', name='cr4_move')
       cr1_rot = Cpt(BeckhoffAxis, ':06', name='cr1_rot')
       cr2_rot = Cpt(BeckhoffAxis, ':07', name='cr2_rot')
       cr3_rot = Cpt(BeckhoffAxis, ':08', name='cr3_rot')
       cr4_rot = Cpt(BeckhoffAxis, ':09', name='cr4_rot')
       com_rot = Cpt(BeckhoffAxis, ':01', name='com_rot')
    vhs = VonHamos_Spec('MFX:VHS:MMB', name='vhs')
"""


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


with safe_load('yagPBT'):
    from happi import Client
    client = Client.from_config()
    yagPBT = client.search(name='xcs_pbt_pim')[0].get()

with safe_load('gon tth with z offset'):
    from xcs.db import xcs_gon as gon
    import numpy as np
    gon_2th=gon.rot_2theta

    def move_gontth(tth=0,z_offset=150,det_position=690):
        """ move the gon 2th when sample has z_offset """
        target_tth = np.rad2deg(np.arctan(((det_position-z_offset)*np.tan(np.deg2rad(tth)))/det_position))
        print('move tth to {}'.format(target_tth)+' base on off cneter {}'.format(z_offset)+' and detector position {}'.format(det_position))	
        try:
            response = input("\nConfirm Move [y/n]: ")
        except Exception as e:
            logger.info("Exception raised: {0}".format(e))
            response = "n"

        if response.lower() != "y":
            logger.info("\nMove cancelled.")
        else:
            logger.debug("\nMove confirmed.")
            gon_2th.umv(target_tth)


with safe_load('Create Aliases'):
   print("test")
   ##from xcs.db import at2l0
   ##at2l0_alias=at2l0
   ##from xcs.db import sb1
   ##create some old, known aliases

   from xcs.db import hx2_pim as  xppyag1
   from xcs.db import um6_pim as yag1
   from xcs.db import hxd_dg2_pim as  yag2
   from xcs.db import xcs_dg3_pim as  yag3
   from xcs.db import xrt_dg3m_pim as  yag3m
   from xcs.db import xcs_sb1_pim as  yag4
   from xcs.db import xcs_sb2_pim as yag5
    
   xppyag1.state.in_states = ['YAG', 'DIODE']
   yag1.state.in_states = ['YAG', 'DIODE']
   yag2.state.in_states = ['YAG', 'DIODE']
   yag3.state.in_states = ['YAG', 'DIODE']
   yag3m.state.in_states = ['YAG', 'DIODE']
   yag4.state.in_states = ['YAG', 'DIODE']
   yag5.state.in_states = ['YAG', 'DIODE']

   from xcs.db import um6_ipm as ipm1
   from xcs.db import hxd_dg2_ipm as ipm2
   from xcs.db import xcs_dg3_ipm as ipm3
   from xcs.db import xcs_sb1_ipm as ipm4
   from xcs.db import xcs_sb2_ipm as ipm5

   #from xcs.db import hx2_slits as xpps1 #missing from xcs.db
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

with safe_load('lxt_fast'):
    def wrapper_set_position(func):
        def wrapped(position):
            result = func(position) 
            print("lxt_fast set the position.")
            print( "RUN encoder set command:"+'\033[1;31m'+"lxt_fast_enc.set_zero()"+'\033[0m')  
            return result
        return wrapped
    lxt_fast.set_current_position = wrapper_set_position(lxt_fast.set_current_position)
    

with safe_load('LADM'):
    from pcdsdevices.xcs_pcdsdevices.ladm import LADM
    from pcdsdevices.positioner import FuncPositioner
    ladm = LADM('XCS:LAM', name='ladm')
    
    ladm.__lowlimX=ladm._set_lowlimX(-10)
    ladm.__hilimX=ladm._set_hilimX(2000)

    ladmTheta = FuncPositioner(name='ladmTheta', move=ladm.moveTheta, get_pos=ladm.wmTheta, set_pos=ladm.setTheta, stop=ladm.stop)
    ladm.theta = ladmTheta

    ladm.XT = FuncPositioner(name='ladmXT', move=ladm.moveX, get_pos=ladm.wmX, set_pos=ladm._setX, egu='mm', limits=(ladm._get_lowlimX, ladm._get_hilimX))
    
    ladm_det_x = IMS('XCS:LAM:MMS:06',name='ladm_det_x')
    ladm_det_y = IMS('XCS:LAM:MMS:07',name='ladm_det_y')

with safe_load('GON'):
    gon_s_rotTheta = IMS('XCS:GON:MMS:03',name='gon_s_rotTheta')
    gon_s_tipChi = IMS('XCS:GON:MMS:05',name='gon_s_tipChi')
    gon_s_tiltPhi = IMS('XCS:GON:MMS:06',name='gon_s_tiltPhi')
    gon_det_vert = IMS('XCS:GON:MMS:10',name='gon_det_vert')
    gon_det_tilt = IMS('XCS:GON:MMS:11',name='gon_det_tilt')
   
     
with safe_load('drift monitor'):
   import numpy as np
   import json
   import sys
   import time
   import os
   import socket
   import logging
   from hutch_python.utils import get_current_experiment
   class drift():
      global ttall,s4statEp,matPV,savefilename,dco
      ttall = EpicsSignal('XCS:TT:01:TTALL')
      s4statEp = EpicsSignal('PPS:FEH1:4:S4STPRSUM')
      matPV = EpicsSignal('LAS:FS4:VIT:DRIFT_CORRECT_VAL')
      savefilename = '/cds/home/opr/xcsopr/experiments/'+get_current_experiment('xcs')+'/drift_log.txt'
      dco = EpicsSignalRO('XCS:SND:DIO:AMPL_9')

      def drift_log(idata):
          currenttime = time.ctime()
          with open(savefilename,'a') as out_f:
              out_f.write(str(idata)+ "," + currenttime.split(" ")[3] +"\n")

      def tt_rough_FB(ttamp_th = 0.1, ipm4_th = 2000, ttfwhmhigh = 200,ttfwhmlow = 50,kp = 0.2,ki = 0.1,kd = 1):#ttamp:timetool signal amplitude threshold, imp2 I0 value threshold, tt_window signal width
         fbvalue = 0 # for drift record
         ave_tt = np.zeros([2,])
         tenshots_tt = np.zeros([120,])#for tt 
         while True:
#            tenshots_tt = np.zeros([1,])#for tt 
            dlen = 0#number of "good shots" for feedback
            pt = 0#time to get the good singal for PI"D"
            while(dlen < 120):
               current_tt, ttamp, ipm4val, ttfwhm,ttintg = drift.get_ttall()
               if(dlen%60 == 0):
                        #print("tt_value",current_tt,"ttamp",ttamp,"ipm4",ipm4val, dlen)         
                  print("\rTT_Value:%0.3f" %current_tt + "   TT_Amp:%0.3f " %ttamp +"   IPM4:%d" %ipm4val,"   Good shot: %d" %dlen,end="")
               if (ttamp > ttamp_th)and(ipm4val > ipm4_th)and(ttfwhm < ttfwhmhigh)and(ttfwhm >  ttfwhmlow)and(current_tt != tenshots_tt[-1,])and(txt.moving == False)and(drift.s4_status() == 0):# for filtering the last one is for when DAQ is stopping
                  tenshots_tt[dlen %120] = current_tt
                  dlen +=1

               pt = pt + 1 
               time.sleep(0.01)
#            tenshots_tt = np.delete(tenshots_tt,0)
            ave_tt[1,] = ave_tt[0,]
            ave_tt[0,] = np.mean(tenshots_tt)
            print("\nMoving average of timetool value:", ave_tt)
            fb_val = drift.pid_control(kp,ki,kd,ave_tt,pt)#calculate the feedback value

            if(round(lxt(),13)==-(round(txt(),13)) and (txt.moving == False) and(drift.s4_status() == 0) ):#check not lxt or during motion of lxt_ttc and the feedback works only when lxt = -txt (lxt_ttc is ok)
               ave_tt_second=-((fb_val)*1e-12)
               drift.matlabPV_FB(ave_tt_second)
               print('\033[1;31m' +  "feedback %f ps"%fb_val + '\033[0m')
               fbvalue = ave_tt + fbvalue# for record
               drift.drift_log(str(fbvalue))# for record
         return
        
      def tt_rough_FB_SND(ttamp_th = 0.01, snd_th = 500, ttfwhmhigh = 120,ttfwhmlow = 100,kp = 0.2,ki = 0.1,kd = 1):
         fbvalue = 0 # for drift record
         ave_tt = np.zeros([2,])
         tenshots_tt = np.zeros([120,])#for tt 
         while True:
#            tenshots_tt = np.zeros([1,])#for tt 
            dlen = 0#number of "good shots" for feedback
            pt = 0#time to get the good singal for PI"D"
            while(dlen < 120):
               current_tt, ttamp, sndval, ttfwhm,ttintg = drift.get_ttall_snd()
               if(dlen%60 == 0):
                        #print("tt_value",current_tt,"ttamp",ttamp,"ipm4",ipm4val, dlen)         
                  print("\rTT_Value:%0.3f" %current_tt + "   TT_Amp:%0.3f " %ttamp +"   SND DCO:%d" %sndval,"   Good shot: %d" %dlen,end="")
               if (ttamp > ttamp_th)and(sndval > snd_th)and(ttfwhm < ttfwhmhigh)and(ttfwhm >  ttfwhmlow)and(current_tt != tenshots_tt[-1,])and(txt.moving == False)and(drift.s4_status() == 0):# for filtering the last one is for when DAQ is stopping
                  tenshots_tt[dlen %120] = current_tt
                  dlen +=1

               pt = pt + 1 
               time.sleep(0.01)
#            tenshots_tt = np.delete(tenshots_tt,0)
            ave_tt[1,] = ave_tt[0,]
            ave_tt[0,] = np.mean(tenshots_tt)
            print("\nMoving average of timetool value:", ave_tt)
            fb_val = drift.pid_control(kp,ki,kd,ave_tt,pt)#calculate the feedback value

            if(round(lxt(),13)==-(round(txt(),13)) and (txt.moving == False) and(drift.s4_status() == 0) ):#check not lxt or during motion of lxt_ttc and the feedback works only when lxt = -txt (lxt_ttc is ok)
               ave_tt_second=-((fb_val)*1e-12)
               drift.matlabPV_FB(ave_tt_second)
               print('\033[1;31m' +  "feedback %f ps"%fb_val + '\033[0m')
               fbvalue = ave_tt + fbvalue# for record
               drift.drift_log(str(fbvalue))# for record
         return

      def s4_status():
         #s4stat = EpicsSignal('PPS:FEH1:4:S4STPRSUM')
         s4stat = s4statEp.get()
         return s4stat# 0 is out, 4 is IN

  
      def pid_control(kp,ki,kd,ave_data,faketime):
         fd_value = kp*ave_data[0,] + ki*(np.sum(ave_data[:,]))+kd*((ave_data[1,]-ave_data[0,])/faketime)
         return fd_value
      def matlabPV_FB(feedbackvalue):#get and put timedelay signal
         #matPV = EpicsSignal('LAS:FS4:VIT:DRIFT_CORRECT_VAL')
         org_matPV = matPV.get()#the matlab PV value before FB
         fbvalns = feedbackvalue * 1e+9#feedback value in ns
         fbinput = org_matPV + fbvalns#relative to absolute value
         matPV.put(fbinput)
         return

      def get_ttall():#get timetool related signal
         ttdata = ttall.get()
         current_tt = ttdata[1,]
         ttamp = ttdata[2,]
         ipm4val = ttdata[3,]
         ttfwhm = ttdata[5,]
         ttintg = ttdata[6,]
         return current_tt, ttamp, ipm4val, ttfwhm, ttintg

      def get_ttall_snd():#get timetool related signal
         ttdata = ttall.get()
         current_tt = ttdata[1,]
         ttamp = ttdata[2,]
         sndval = dco.get()
         ttfwhm = ttdata[5,]
         ttintg = ttdata[6,]
         return current_tt, ttamp, sndval, ttfwhm, ttintg


      def timing_check():###############Check the laser lock and time delay status 
         tttime = EpicsSignal('LAS:FS4:VIT:FS_TGT_TIME')#target time
         tttact = EpicsSignal('LAS:FS4:VIT:FS_CTR_TIME')#actual control time
         tttphase = EpicsSignal('LAS:FS4:VIT:PHASE_LOCKED')#phase
         if(round(tttime.get(),1)==round(tttact.get(),1) and (tttphase.get() == 1)):
            return 1 ## lxt is ok for the target position
         elif(round(tttime.get(),1)!=round(tttact.get(),1) or (tttphase.get() != 1)):
            return 0

      def get_correlation(numshots):##get timetool correlation from Event builder
         ttdataall = np.zeros([numshots,])
         ipm4values = np.zeros([numshots,])
         ii = 0
         while (ii < numshots):
            ttall = EpicsSignal('XCS:TT:01:EVENTBUILD.VALA')
            ttdata = ttall.get()
            ttamp = ttdata[2,]
            ipm4val = ttdata[1,]
            ttfwhm = ttdata[5,]
            ttintg = ttdata[11,]
            if(ipm4val > 200): 
               ttdataall[ii,] = ttintg
               ipm4values[ii,] = ipm4val
               ii = ii + 1
            time.sleep(0.008)
    #print(ttdata,ipm4values)
         ttipmcorr = np.corrcoef(ttdataall,ipm4values) 
         return ttipmcorr[0,1]
################################################################################################################################
      def autott_find(ini_delay = 50e-9, testshot = 360, ttsiglevel = -0.2, calic = 1.1, inisearch = 25, lxttimeout = 4, ccm = False):
        #"""
        #tt signal find tool the ini_delay is now input argument maybe for pink beam, lxttimeout the time to wait for lxt motion, test shot: 
        #number of shots to accumulate for getting correlation, initial delay the step size of the initial large search. 
        #inisearch: scan range  for the initial big step search, 
        #ttsiglevel: correlation coeffcient. 
        #If there is correlation, typically the signal level is -0.9, which is relatively large so you don't need to care the signal level. 
        #"""
         ccmstat = ccm
         if ccm == False:
            tt_ty.umv(-16.1)
         elif ccm == True:
            tt_ty.umv(-8.6)
         if lxt() != 0:
            print('\033[1m'+ "Set current position to 0 to search" + '\033[0m') 
            return
         elif lxt() ==0:
            #tt_y.umv(-16.1)#LuAG to find tt signal
            delayinput = ini_delay#Search window
            i = 0#iteration time
            print('\033[1m'+ "Checking white light Bg level"+'\033[0m')
                #lom.yag.insert()#insert the YAG to block X-rays before the timetool target
                #while(lom.yag.inserted == False ):
                #    time.sleep(1)
                #    print('Waiting for YAG getting in')
            ttdata = np.zeros([testshot,])
            ii = 0
            print("Getting the white light Bg level")
                
               

                #######Finding the initial correlation switching point####################

            
            print('\033[1m'+ "Searching the correlation switch point first"+'\033[0m')
            ttcorr = drift.get_correlation(testshot)
                    #print(ii)
                
            print(ttcorr)
          
            while(1):#20ns search until finding the correlation switched
               bs = (ttcorr < ttsiglevel)  #input the current correlation
               print(i)
               if i == 0:# for the initialization
                  prebs = bs
                       
                       
               if ((i < inisearch)and(prebs == bs)):
                    #First search in 100 ns. 100 ns is too large. 
                    #If cannot find in 10 iteration need to check the other side
                  print(bs)
                  if bs == False:
                     delayinput = -1 * abs(delayinput)
                     lxt.mvr(delayinput)
                     while(lxt.moving == True):
                        time.sleep(0.01)
                     i = i + 1
                  
                     #time.sleep(lxttimeout)
                     print(f"Searching the negative correlation with 10ns. Number of iteration:{i}")
                  elif bs == True:#find non-correlation
                     delayinput = abs(delayinput)
                     lxt.mvr(delayinput)
                     while(lxt.moving == True):
                        time.sleep(0.01)
                     i = i + 1
                     #time.sleep(lxttimeout)
                     print(f"Searching the positive or no correlation with 10ns. Number of iteration:{i}")
                  
                  while(drift.timing_check() != 1):### waiting for the lxt motion compledted
                     time.sleep(0.1)
                  time.sleep(0.1)
                  ttcorr = drift.get_correlation(testshot)
                  bs = (ttcorr < ttsiglevel) #input the current correlation
                #print(bs,(ttcorr-ttsiglevel))
               elif( i >= inisearch)and(prebs == bs):
                  print('\033[1m'+"the tt signal is far from 500 ns range, please search 100 ns range"+'\033[0m')  
                  return
               elif(prebs != bs):
                  print('\033[1m'+"Switch to binary search"+'\033[0m')
                  break
            #the correlation change?
          
##########################binary search part######################
            while(abs(delayinput) > 1.0e-12):#binary search from 10ns to 5ps
               print('\033[1m'+"Binary search"+'\033[0m')
               time.sleep(0.1)
               ttcorr = drift.get_correlation(testshot)
               bs = (ttcorr < ttsiglevel) #input the current correlation:True negative, False positive
               if bs == False:
                  delayinput = -1 * abs(delayinput)
                  delayinput = delayinput/2
                  lxt.mvr(delayinput)
                  while(lxt.moving == True):
                     time.sleep(0.01)
                  while(drift.timing_check() != 1):### waiting for the lxt motion compledted
                     time.sleep(0.01)
                  print(f"Timewindow: {delayinput}")
                 #delayinput = delayinput/2
                  i = i + 1
                  prebs = False
                  inidirection = "n"
                  print(f"Number of iteration:{i}")
                
               elif bs == True:
                  delayinput = abs(delayinput)
                  delayinput = delayinput/2
                  lxt.mvr(delayinput)
                  while(lxt.moving == True):
                     time.sleep(0.01)
                  while(drift.timing_check() != 1):### waiting for the lxt motion compledted
                     time.sleep(0.01)
                  print(f"Timewindow: {delayinput}")
                  #delayinput = delayinput/2
                  i = i + 1
                  prebs = True
                  inidirection = "p"
                  print(f"Number of iteration:{i}")
         drift.tt_recover(scanrange = 10e-12,stepsize = -0.5e-12,direction = inidirection,testshot = 240, ccm = ccmstat)  
         return

      def autott_find_pink(ini_delay = 10e-9, testshot = 360, ttsiglevel = 0.96, calic = 1.0):#tt signal find tool the ini_delay is now input argument maybe for pink bea
         if lxt() != 0:
            print('\033[1m'+ "Set current position to 0 to search" + '\033[0m') 
            return
         elif lxt() ==0:
            tt_ty.umv(-16.1)#LuAG to find tt signal
            delayinput = ini_delay#Search window
            i = 0#iteration time
            print('\033[1m'+ "Checking white light Bg level"+'\033[0m')
            yag4.insert()#insert the YAG to block X-rays before the timetool target
            while(yag4.inserted == False ):
               time.sleep(1)
               print('Waiting for YAG getting in')
            ttdata = np.zeros([testshot,])
            ii = 0
            print("Getting the white light Bg level")
            for ii in range(testshot):###Get the white light Bg level without X-rays
               current_tt, ttamp, ipm4val, ttfwhm, ttintg = drift.get_ttall()#get 240 shots to find timetool signal
               ttdata[ii,] = ttintg
               time.sleep(0.008)
            ttbg = np.mean(ttdata)# average white ROI signal without X-rays
            yag4.remove()
            while(yag4.removed == False ):####Removing lom YAG
               time.sleep(1)
               print('Waiting for lom YAG removed')


         
	#######Finding the initial correlation switching point####################


            print('\033[1m'+ "Searching the correlation switch point first"+'\033[0m')
            for ii in range(testshot):###Get the white light intensity with X-rays
               current_tt, ttamp, ipm4val, ttfwhm, ttintg = drift.get_ttall()#get 240 shots to find timetool signal
               ttdata[ii,] = ttintg
               time.sleep(0.008)
	    #print(ii)
            ttroi = np.mean(ttdata)# average white ROI signal with X-rays
            print(ttroi)
            while(1):#20ns search until finding the correlation switched
               bs = ((ttroi - ttbg * ttsiglevel) < 0) #input the current correlation
               print(i)
               if i == 0:# for the initialization
                  prebs = bs
	       
                  print((i < 10)and(prebs == bs))
               if ((i < 25)and(prebs == bs)):#First search in 100 ns. 100 ns is too large. If cannot find in 10 iteration need to check the other side
                  print(bs)
                  if bs == False:#if positive or no-correlation
                     delayinput = -1 * abs(delayinput)
                     lxt.mvr(delayinput)
                     print("test")
                     i = i + 1
                     print(f"Searching the negative correlation with 10ns. Number of iteration:{i}")
                  elif bs == True:#find non-correlation from the negative
                     delayinput = abs(delayinput)
                     lxt.mvr(delayinput)
                     i = i + 1
                     print(f"Searching the positive or no correlation with 10ns. Number of iteration:{i}")
                  while(drift.timing_check() != 1):### waiting for the lxt motion compledte
                     time.sleep(0.1)
                  for ii in range(testshot):###Get the white light intensity with X-rays
                     current_tt, ttamp, ipm4val, ttfwhm, ttintg = drift.get_ttall()#get 240 shots to find timetool signal
                     ttdata[ii,] = ttintg
                     time.sleep(0.008)
                  ttroi = np.mean(ttdata)# average white ROI signal with X-rays
                  bs = ((ttroi - ttbg * ttsiglevel) < 0) #input the current correlation
                  print(bs,ttroi-ttbg*ttsiglevel)
            
               elif( i >= 25)and(prebs == bs):
                  print('\033[1m'+"the tt signal is far from 100 ns range, please search 100 ns range"+'\033[0m')  
                  return
               elif(prebs != bs):
                  print('\033[1m'+"Switch to binary search"+'\033[0m')
                  break
	    #the correlation change?
	  
	##########################binary search part######################
            while(abs(delayinput) > 1e-12):#binary search from 10ns to 5ps
               print('\033[1m'+"Binary search"+'\033[0m')
               for ii in range(testshot):###Get the white light intensity with X-rays
                  current_tt, ttamp, ipm4val, ttfwhm, ttintg = drift.get_ttall()#get 240 shots to find timetool signal
                  ttdata[ii,] = ttintg
                  time.sleep(0.008)
               ttroi = np.mean(ttdata)# average white ROI signal with X-rays
               bs = ((ttroi - ttbg * ttsiglevel) < 0) #input the current correlation
               if bs == False:
                  delayinput = -1 * abs(delayinput)
                  delayinput = delayinput/2
                  lxt.mvr(delayinput)
                  print(f"Timewindow: {delayinput}")

                  i = i + 1
                  prebs = False
                  inidirection = "n"
                  print(f"Number of iteration:{i}")

               elif bs == True:
                  delayinput = abs(delayinput)
                  delayinput = delayinput/2
                  lxt.mvr(delayinput)
                  print(f"Timewindow: {delayinput}")

                  i = i + 1
                  prebs = True
                  inidirection = "p"
                  print(f"Number of iteration:{i}")
               while(drift.timing_check() != 1):### waiting for the lxt motion compledted
                  time.sleep(0.1)
            drift.tt_recover(scanrange = 10e-12,stepsize = -0.5e-12,direction = inidirection,testshot = 360) 
            return


###############################################################################################################################
      def tt_recover(scanrange = 5e-12,stepsize = -0.5e-12,direction = "p",testshot = 240, ccm = False):#For tt_signal recover in 10 ps
         if ccm == False:
            tt_ty.umv(-16.1)#LuAG to find tt signal
         elif ccm == True:
            tt_ty.umv(-8.6)
         originaldelay = lxt()
         if direction == "n":
            print("Search tt signal from positive to negative")
            lxt.mvr(scanrange)
            time.sleep(0.5)
         elif direction == "p":
            lxt.mvr(-1*scanrange)
            print("Search tt signal from negative to positive")
            stepsize = -1 * stepsize
            time.sleep(0.5)
         j = 0
         while(abs(stepsize * j) < abs(scanrange * 2) ):
            ttdata = np.zeros([testshot,])
            ii = 0
            for ii in range(testshot):
                current_tt, ttamp, ipm4val, ttfwhm,ttintg = drift.get_ttall()#get 240 shots to find timetool signal
                if (ttamp > 0.03)and(ttfwhm < 130)and(ttfwhm >  100)and(ttamp<2):
                    ttdata[ii,] = ttamp
                time.sleep(0.008)
            print(ttdata)
            if np.count_nonzero(ttdata[:,]) > 30:#1/4 shots have timetool signal
                print("Found timetool signal and set current lxt to 0")
                print(f"we will reset the current {lxt()} position to 0")
                lxt.set_current_position(0)
                #ltt_y.umv(67.1777)#Switch to YAG
                print("Please run drift.tt_rough_FB()")
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
         print("The script cannot find the timetool signal in this range. Try las.autott_find()")        
          
        
         return
##############################################################################################################################
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


#with safe_load('gige hdf5 beta'):
#    from pcdsdevices.areadetector.detectors import PCDSHDF5BlueskyTriggerable
#    xcs_gige_lj1_hdf5 = PCDSHDF5BlueskyTriggerable(
#        'XCS:GIGE:LJ1:',
#        name='xcs_gige_lj1_hdf5',
#        write_path='/cds/data/iocData/ioc-xcs-gige-lj1',
#    )


