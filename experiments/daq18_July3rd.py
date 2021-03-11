from subprocess import check_output

class User():
    
    def ImagerHdf5Print(self, imager):
        print('Enabled',imager.hdf51.enable.get())
        print('File path',imager.hdf51.file_path.get())
        print('File name',imager.hdf51.file_name.get())
        print('File template (should be %s%s_%d.h5)',imager.hdf51.file_template.get())
        print('File number',imager.hdf51.file_number.get())
        print('Frame to capture per file',imager.hdf51.num_capture.get())
        print('autoincrement ',imager.hdf51.auto_increment.get())
        print('file_write_mode ',imager.hdf51.file_write_mode.get())
        #IM1L0:XTES:CAM:HDF51:Capture_RBV 0: done, 1: capturing
        print('captureStatus ',imager.hdf51.capture.get())

    def ImagerHdf5Prepare(self, imager, baseName=None, pathName=None, nImages=None):
        if imager.hdf51.enable.get() != 'Enabled':
            imager.hdf51.enable.set(1)
        if pathName is not None:
            imager.hdf51.file_path.set(pathName)
        if baseName is not None:
            imager.hdf51.file_name.set(baseName)
        else:
            expname = subprocess.check_output('get_curr_exp').decode('utf-8').replace('\n','')
            runnr = int(subprocess.check_output('get_lastRun').decode('utf-8').replace('\n',''))
            imager.hdf51.file_name.set('%s_Run%03d'%(expname, runnr+1))

        imager.hdf51.file_template.set('%s%s_%d.h5')
        imager.hdf51.auto_increment.set(1)
        imager.hdf51.file_write_mode.set(2)
        if nImages is not None:
            self.ImagerHdf5Nimages(imager, nImages=nImages)

    def ImagerHdf5Nimages(self, imager, nImages=None, nSec=None):
        if nImages is not None:
            imager.hdf51.num_capture.set(nImages)
        if nSec is not None:
            if imager.cam.acquire.get() > 0:
                rate = imager.cam.array_rate.get()
                imager.hdf51.num_capture.set(nSec*rate)
            else:
                print('Imager is not acquiring, cannot use rate to determine number of recorded frames')

    def ImagerHdf5Write(self, imager):
        if imager.cam.acquire.get() == 0:
            imager.cam.acquire.set(1)
        imager.hdf51.capture.set(1)
    
    #
    #
    #

    def ImagerStatsStop(self, imager):
        imager.stats1.enable.set(0)

    def ImagerStatsSetThreshold(self, imager, nSigma=1):
        imager.stats1.enable.set(1)
        computeStat = imager.stats1.compute_statistics.get()
        imager.stats1.compute_statistics.set(1)
        mean = imager.stats1.mean_value.get()
        sigma = imager.stats1.sigma.get()
        imager.stats1.centroid_threshold.set(mean+sigma*nSigma)
        imager.stats1.compute_statistics.set(computeStat)

    def ImagerStatsPrepare(self, imager, threshold=None):
        if imager.stats1.enable.get() != 'Enabled':
            imager.stats1.enable.set(1)
        if threshold is not None:
            if imager.stats1.compute_centroid.get() != 'Yes':
                imager.stats1.compute_centroid.set(1)
            imager.stats1.centroid_threshold.set(threshold)
        imager.stats1.compute_profile.set(1)
        imager.stats1.compute_centroid.set(1)

    def ImagerStatsPrint(self, imager):
        print('enabled:', imager.stats1.enable.get())
        if imager.stats1.enable.get() == 'Enabled':
            if imager.stats1.compute_statistics.get() == 'Yes':
                #IM1L0:XTES:CAM:Stats1:MeanValue_RBV
                #IM1L0:XTES:CAM:Stats1:SigmaValue_RBV
                print('Mean', imager.stats1.mean_value.get())
                print('Sigma', imager.stats1.sigma.get())
            if imager.stats1.compute_centroid.get() == 'Yes':
                print('Threshold', imager.stats1.centroid_threshold.get())
                #IM1L0:XTES:CAM:Stats1:CentroidX_RBV
                #IM1L0:XTES:CAM:Stats1:CentroidY_RBV
                #IM1L0:XTES:CAM:Stats1:SigmaX_RBV
                #IM1L0:XTES:CAM:Stats1:SigmaY_RBV
                print('X,y', imager.stats1.centroid.get())
                print('sigma x', imager.stats1.sigma_x.get())
                print('sigma y', imager.stats1.sigma_y.get())
            if imager.stats1.compute_profile.get() == 'Yes':
                #IM1L0:XTES:CAM:Stats1:CursorX
                #IM1L0:XTES:CAM:Stats1:CursorY
                print('profile cursor values: ',imager.stats1.cursor.get())
                #IM1L0:XTES:CAM:Stats1:ProfileAverageX_RBV
                #IM1L0:XTES:CAM:Stats1:ProfileAverageY_RBV
                #IM1L0:XTES:CAM:Stats1:ProfileThresholdX_RBV
                #IM1L0:XTES:CAM:Stats1:ProfileThresholdY_RBV
                #IM1L0:XTES:CAM:Stats1:ProfileCentroidX_RBV
                #IM1L0:XTES:CAM:Stats1:ProfileCentroidY_RBV
                #IM1L0:XTES:CAM:Stats1:ProfileCursorX_RBV
                #IM1L0:XTES:CAM:Stats1:ProfileCursorY_RBV
                print('profile cursor: ',imager.stats1.profile_cursor.get())
                print('profile centroid: ',imager.stats1.profile_centroid.get())
                if imager.stats1.compute_centroid.get() == 'Yes':
                    print('profile threshold: ',imager.stats1.profile_threshold.get())
                    print('profile avergage: ',imager.stats1.profile_average.get())
