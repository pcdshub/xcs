import numpy as np
import matplotlib.pyplot as plt
from ophyd import EpicsSignal
from pcdsdevices import analog_signals

aio = analog_signals.Acromag(name = 'xcs_aio', prefix = 'XCS:USR')

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



def snd_correlation(nshots=240):
    sndall=EpicsSignal('XCS:TT:01:SNDDIO.VALA')
    ipm5_vals=np.zeros(nshots)
    dd_vals=np.zeros(nshots) #ch15                                                                                                                
    do_vals=np.zeros(nshots) #ch9                                                                                                                 
    cc_vals=np.zeros(nshots) #ch14                                                                                                                
    #Ch8, CC (Ch9), Ch10, Ch11, Ch12, Ch13, Ch14, Delay (Ch15), IPM4 Sum, IPM5 Sum.                                                               
    print('Collect {} shots'.format(nshots))
    show_cc()
    for i in range(nshots):
        snddata=sndall.get()
        ipm5_vals[i]=snddata[9,]
        dd_vals[i]=snddata[7,]
        cc_vals[i]=snddata[1,]
        do_vals[i]=snddata[6,]
    do_ref=np.mean(do_vals)
    cc_ref=np.mean(cc_vals)
    coff_cc=cc_ref/do_ref
    print('coefficient CC : {:.2f}'.format(coff_cc))
    plt.figure()
    plt.subplot(2,2,1)
    plt.plot(do_vals,cc_vals,'.')
    plt.grid();
    plt.xlabel('DO signal');
    plt.ylabel('CC signal'); plt.title("CC only")
    show_delay()
    for i in range(nshots):
        snddata=sndall.get()
        ipm5_vals[i]=snddata[9,]
        dd_vals[i]=snddata[7,]
        cc_vals[i]=snddata[1,]
        do_vals[i]=snddata[6,]
    do_ref=np.mean(do_vals)
    dd_ref=np.mean(cc_vals)
    coff_dd=dd_ref/do_ref
    print('coefficient DD : {:.2f}'.format(coff_dd))
    plt.subplot(2,2,2)
    plt.plot(do_vals,dd_vals,'.')
    plt.grid();
    plt.xlabel('DO signal');
    plt.ylabel('DD signal'); plt.title("DD only")

    show_both()
    for i in range(nshots):
        snddata=sndall.get()
        ipm5_vals[i]=snddata[9,]
        dd_vals[i]=snddata[7,]*coff_dd
        cc_vals[i]=snddata[1,]*coff_cc
        do_vals[i]=snddata[6,]
    ratios = 1+(dd_vals-cc_vals)/do_vals
    ratio = np.mean(ratios)
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
