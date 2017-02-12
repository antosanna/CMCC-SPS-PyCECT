#! /usr/bin/env python

import sys,getopt,os
import numpy as np
import Nio
import time
import pyEnsLib
import json
import random
import glob
import re
from datetime import datetime
from asaptools.partition import EqualStride, Duplicate
import asaptools.simplecomm as simplecomm 

#This routine compares the results of several (default=3) new CAM tests
#against the accepted ensemble (generated by pyEC).


def main(argv):


    # Get command line stuff and store in a dictionary
    s="""verbose sumfile= indir= input_globs= tslice= nPC= sigMul= 
         minPCFail= minRunFail= numRunFile= printVarTest popens 
         jsonfile= mpi_enable nbin= minrange= maxrange= outfile= 
         casejson= npick= pepsi_gm test_failure pop_tol= 
         pop_threshold= prn_std_mean lev= eet= json_case= """
    optkeys = s.split()
    try:
        opts, args = getopt.getopt(argv,"h",optkeys)
    except getopt.GetoptError:
        pyEnsLib.CECT_usage()
        sys.exit(2)
  
    
    # Set the default value for options
    opts_dict = {}
    opts_dict['input_globs'] = ''
    opts_dict['indir'] = ''
    opts_dict['tslice'] = 1
    opts_dict['nPC'] = 50
    opts_dict['sigMul'] = 2
    opts_dict['verbose'] = False
    opts_dict['minPCFail'] = 3
    opts_dict['minRunFail'] = 2
    opts_dict['numRunFile'] = 3
    opts_dict['printVarTest'] = False
    opts_dict['popens'] = False
    opts_dict['jsonfile'] = ''
    opts_dict['mpi_enable'] = False
    opts_dict['nbin'] = 40
    opts_dict['minrange'] = 0.0
    opts_dict['maxrange'] = 4.0
    opts_dict['outfile'] = 'testcase.result'
    opts_dict['casejson'] = ''
    opts_dict['npick'] = 10
    opts_dict['pepsi_gm'] = False
    opts_dict['test_failure'] = True
    opts_dict['pop_tol'] = 3.0
    opts_dict['pop_threshold'] = 0.90
    opts_dict['prn_std_mean'] = False
    opts_dict['lev'] = 0
    opts_dict['eet'] = 0
    opts_dict['json_case'] = ''
    # Call utility library getopt_parseconfig to parse the option keys
    # and save to the dictionary
    caller = 'CECT'
    gmonly = False
    opts_dict = pyEnsLib.getopt_parseconfig(opts,optkeys,caller,opts_dict)
    popens = opts_dict['popens']

    # Create a mpi simplecomm object
    if opts_dict['mpi_enable']:
        me=simplecomm.create_comm()
    else:
        me=simplecomm.create_comm(not opts_dict['mpi_enable'])

    # Print out timestamp, input ensemble file and new run directory
    dt=datetime.now()
    verbose = opts_dict['verbose']
    if me.get_rank()==0:
	print '--------pyCECT--------'
	print ' '
	print dt.strftime("%A, %d. %B %Y %I:%M%p")
	print ' '
	print 'Ensemble summary file = '+opts_dict['sumfile']
	print ' '
	print 'Testcase file directory = '+opts_dict['indir']    
	print ' '
	print ' '

    # Ensure sensible EET value
    if not opts_dict['eet'] >= 0:
        pyEnsLib.CECT_usage()
        sys.exit(2)

  
    ifiles=[]
    in_files=[]
    # Random pick pop files from not_pick_files list
    if opts_dict['casejson']:
       with open(opts_dict['casejson']) as fin:
            result=json.load(fin)
            in_files_first=result['not_pick_files']
            in_files=random.sample(in_files_first,opts_dict['npick'])
            print 'Testcase files:'
            print '\n'.join(in_files)
           
    elif opts_dict['json_case']: 
       json_file=opts_dict['json_case']
       if (os.path.exists(json_file)):
          fd=open(json_file)
          metainfo=json.load(fd)
          if 'CaseName' in metainfo:
              casename=metainfo['CaseName']
	      if (os.path.exists(opts_dict['indir'])):
		 for name in casename: 
		     wildname='*.'+name+'.*'
		     full_glob_str=os.path.join(opts_dict['indir'],wildname)
		     glob_file=glob.glob(full_glob_str)
		     in_files.extend(glob_file)
       print in_files
    else: 
       wildname='*'+opts_dict['input_globs']+'*'
       # Open all input files
       if (os.path.exists(opts_dict['indir'])):
          full_glob_str=os.path.join(opts_dict['indir'],wildname)
          glob_files=glob.glob(full_glob_str)
          in_files.extend(glob_files)
          #in_files_temp=os.listdir(opts_dict['indir'])
    in_files.sort()

    if popens:
        #Partition the input file list 
        in_files_list=me.partition(in_files,func=EqualStride(),involved=True)

    else:
        # Random pick non pop files
        in_files_list=pyEnsLib.Random_pickup(in_files,opts_dict)
        #in_files_list=in_files

    for frun_file in in_files_list:
         if frun_file.find(opts_dict['indir']) != -1:
            frun_temp=frun_file
         else:
            frun_temp=opts_dict['indir']+'/'+frun_file
         if (os.path.isfile(frun_temp)):
             ifiles.append(Nio.open_file(frun_temp,"r"))
         else:
             print "COULD NOT LOCATE FILE " +frun_temp+" EXISTING"
             sys.exit()
    
    if popens:
        
        # Read in the included var list
        Var2d,Var3d=pyEnsLib.read_jsonlist(opts_dict['jsonfile'],'ESP')
        print ' '
        print 'Z-score tolerance = '+'{:3.2f}'.format(opts_dict['pop_tol'])
        print 'ZPR = '+'{:.2%}'.format(opts_dict['pop_threshold'])
        zmall,n_timeslice=pyEnsLib.compare_raw_score(opts_dict,ifiles,me.get_rank(),Var3d,Var2d)  
        #zmall = np.concatenate((Zscore3d,Zscore2d),axis=0)
        np.set_printoptions(threshold=np.nan)

        if opts_dict['mpi_enable']:
            zmall = pyEnsLib.gather_npArray_pop(zmall,me,(me.get_size(),len(Var3d)+len(Var2d),len(ifiles),opts_dict['nbin'])) 
            if me.get_rank()==0:
                fout = open(opts_dict['outfile'],"w")
		for i in range(me.get_size()):
		    for j in zmall[i]:
                        np.savetxt(fout,j,fmt='%-7.2e')
    else:
	# Read all variables from the ensemble summary file
	ens_var_name,ens_avg,ens_stddev,ens_rmsz,ens_gm,num_3d,mu_gm,sigma_gm,loadings_gm,sigma_scores_gm,is_SE_sum=pyEnsLib.read_ensemble_summary(opts_dict['sumfile']) 

	if len(ens_rmsz) == 0:
	    gmonly = True
	# Add ensemble rmsz and global mean to the dictionary "variables"
	variables={}
	if not gmonly:
	    for k,v in ens_rmsz.iteritems():
		pyEnsLib.addvariables(variables,k,'zscoreRange',v)

	for k,v in ens_gm.iteritems():
	    pyEnsLib.addvariables(variables,k,'gmRange',v)

	# Get 3d variable name list and 2d variable name list seperately
	var_name3d=[]
	var_name2d=[]
	for vcount,v in enumerate(ens_var_name):
	  if vcount < num_3d:
	    var_name3d.append(v)
	  else:
	    var_name2d.append(v)

	# Get ncol and nlev value
	npts3d,npts2d,is_SE=pyEnsLib.get_ncol_nlev(ifiles[0])
 
        if (is_SE ^ is_SE_sum):
           print 'Warning: please note the ensemble summary file is different from the testing files, they use different grids'
           
     
	# Compare the new run and the ensemble summary file to get rmsz score
	results={}
	countzscore=np.zeros(len(ifiles),dtype=np.int32)
	countgm=np.zeros(len(ifiles),dtype=np.int32)
	if not gmonly:
	    for fcount,fid in enumerate(ifiles): 
		otimeSeries = fid.variables 
		for var_name in ens_var_name: 
		    orig=otimeSeries[var_name]
		    Zscore,has_zscore=pyEnsLib.calculate_raw_score(var_name,orig[opts_dict['tslice']],npts3d,npts2d,ens_avg,ens_stddev,is_SE,opts_dict,0,0,0) 
		    if has_zscore:
			# Add the new run rmsz zscore to the dictionary "results"
			pyEnsLib.addresults(results,'zscore',Zscore,var_name,'f'+str(fcount))


	    # Evaluate the new run rmsz score if is in the range of the ensemble summary rmsz zscore range
	    for fcount,fid in enumerate(ifiles):
		countzscore[fcount]=pyEnsLib.evaluatestatus('zscore','zscoreRange',variables,'ens',results,'f'+str(fcount))

	# Calculate the new run global mean
	mean3d,mean2d,varlist=pyEnsLib.generate_global_mean_for_summary(ifiles,var_name3d,var_name2d,is_SE,opts_dict['pepsi_gm'],opts_dict)
	means=np.concatenate((mean3d,mean2d),axis=0)

	# Add the new run global mean to the dictionary "results"
	for i in range(means.shape[1]):
	    for j in range(means.shape[0]):
		pyEnsLib.addresults(results,'means',means[j][i],ens_var_name[j],'f'+str(i))

	# Evaluate the new run global mean if it is in the range of the ensemble summary global mean range
	for fcount,fid in enumerate(ifiles):
	    countgm[fcount]=pyEnsLib.evaluatestatus('means','gmRange',variables,'gm',results,'f'+str(fcount))
      
	# Calculate the PCA scores of the new run
	new_scores,var_list=pyEnsLib.standardized(means,mu_gm,sigma_gm,loadings_gm,ens_var_name,opts_dict,ens_avg,me)
	run_index=pyEnsLib.comparePCAscores(ifiles,new_scores,sigma_scores_gm,opts_dict,me)
        # If there is failure, plot out the 3 variables that have the largest sum of standardized global mean
        #print in_files_list
        if opts_dict['prn_std_mean']:
            if len(run_index)>0:
               json_file=opts_dict['json_case']
	       if (os.path.exists(json_file)):
		  fd=open(json_file)
		  metainfo=json.load(fd)
		  caseindex=metainfo['CaseIndex']
		  enspath=str(metainfo['EnsPath'][0])
		  #print caseindex
		  if (os.path.exists(enspath)):
                     i=0
                     comp_file=[]
                     search = '\.[0-9]{3}\.'
                     for name in in_files_list:
                        s=re.search(search,name)
                        in_files_index=s.group(0)
                        if in_files_index[1:4] in caseindex:
                           ens_index=str(caseindex[in_files_index[1:4]])
                           wildname='*.'+ens_index+'.*'
                           full_glob_str=os.path.join(enspath,wildname)
                           glob_file=glob.glob(full_glob_str)
                           comp_file.extend(glob_file)
	             print "comp_file=",comp_file		 
		     pyEnsLib.plot_variable(in_files_list,comp_file,opts_dict,var_list,run_index,me)

	# Print out 
	if opts_dict['printVarTest']:
	    print '*********************************************** '
	    print 'Variable-based testing (for reference only - not used to determine pass/fail)'
	    print '*********************************************** '
	    for fcount,fid in enumerate(ifiles):
		print ' '
		print 'Run '+str(fcount+1)+":"
		print ' '
		if not gmonly:
		    print '***'+str(countzscore[fcount])," of "+str(len(ens_var_name))+' variables are outside of ensemble RMSZ distribution***'
		    pyEnsLib.printsummary(results,'ens','zscore','zscoreRange',(fcount),variables,'RMSZ')
		    print ' '
		print '***'+str(countgm[fcount])," of "+str(len(ens_var_name))+' variables are outside of ensemble global mean distribution***'
		pyEnsLib.printsummary(results,'gm','means','gmRange',fcount,variables,'global mean')
		print ' '
		print '----------------------------------------------------------------------------'
    if me.get_rank() == 0:
	print ' '
	print "Testing complete."
	print ' '

if __name__ == "__main__":
    main(sys.argv[1:])
