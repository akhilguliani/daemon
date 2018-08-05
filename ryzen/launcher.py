""" Helper functions to parse and launch programs presented in an input file """
import os
from multiprocessing import Process
from time import time
import shlex
import subprocess
import psutil

def parse_file(file_path):
    """Parse input file and return list of programs with thier dir annd shares"""
    retval = []
    with open(file_path) as pfile:
        count = 1
        local = []
        for line in pfile:
            if line[0] == '#':
                # Adding comments in file
                continue
            if "@" in line:
                if local != []:
                    retval.append(local)
                local = []
                count = 1
                continue
            if count == 1:
                # append directory
                local.append(line.strip())
            elif count == 2:
                # extract CMD line parameters
                local.append(list(shlex.split(line.strip())))
            elif count == 3:
                # extract shares
                shares = int(line)
                if shares < 0:
                    shares = 0
                if shares > 100:
                    shares = 100
                local.append(shares)
            elif count == 4:
                # extract shares
                prio = None
                theline = line.strip()
                if theline == "High":
                    prio = -19
                elif theline == "Medium":
                    prio = 0
                elif theline == "Low":
                    prio = 20
                local.append(prio)
                # print(local)
            count += 1
    # print("__\n", retval)
    return retval

def launch_on_core(process_info, cpu=0):
    """ Take the output from parse_file and launch the process on a core=cpu """
    pcwd = process_info[0]
    pargs = process_info[1]
    ret = psutil.Popen(args=pargs, cwd=pcwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ret.cpu_affinity([cpu])
    ret.nice(process_info[3]) # if we need to add priorities
    return ret

def run_on_core(process_info, cpu=0):
    """ Take the output from parse_file and launch the process on a core=cpu """
    p = launch_on_core(process_info, cpu)
    p_dict_loc = p.as_dict()
    proc_dict = {}
    proc_dict[p_dict_loc['pid']] = p_dict_loc

    def print_time(proc):
        """ Print Process Info on compeletion """
        end_time = time()
        p_dic = proc_dict[proc.pid]
        print(p_dic['name'], p_dic['pid'], p_dic['cpu_num'], str(end_time - p_dic['create_time']))

    psutil.wait_procs([p], timeout=None, callback=print_time)
    return

def wait_for_procs(procs, callback_fn):
    gone, alive = psutil.wait_procs(procs, timeout=None, callback=callback_fn)
    for _p in alive:
        _p.kill()

def run_on_all_cores(process_info, cores=[0]):
    """ Take the output from parse_file and launch the process on a cores=cpu """
    p_list = []
    proc_dict = {}
    for cpu in cores:
        p = launch_on_core(process_info, cpu)
        p_dict_loc = p.as_dict()
        proc_dict[p_dict_loc['pid']] = p_dict_loc
        p_list.append(p)

    def print_time(proc):
        """ Print Process Info on compeletion """
        end_time = time()
        p_dic = proc_dict[proc.pid]
        print(p_dic['name'], p_dic['pid'], p_dic['cpu_num'], str(end_time - p_dic['create_time']))

    psutil.wait_procs(p_list, timeout=None, callback=print_time)
    return

def run_on_core_forever(process_info, cpu=0):
    """ Take the output from parse_file and launch the process on a core=cpu """
    p = launch_on_core(process_info, cpu)

    def restart(proc):
        """ Infinate recursive callback"""
        print("restarting ", str(proc.pid))
        run_on_core_forever(process_info, cpu)

    psutil.wait_procs([p], timeout=None, callback=restart)
    return

def run_multiple_on_cores(process_info_list, cores=None):
    """ Take the output from parse_file and launch the processes on cores=[cpu,...] """
    # Ensure size of cores and process_info_list is same
    if len(process_info_list) > psutil.cpu_count(logical=False):
        print("More Processess than cores, can't run em all")
        exit(1)
    # one more check for len(process_info_list) == len(cores)
    if cores is None:
        cores = range(len(process_info_list))

    p_list = []
    proc_dict = {}
    for cpu, process_info in zip(cores, process_info_list):
        p = launch_on_core(process_info, cpu)
        p_dict_loc = p.as_dict()
        proc_dict[p_dict_loc['pid']] = p_dict_loc
        p_list.append(p)

    def print_time(proc):
        """ Print Process Info on compeletion """
        end_time = time()
        p_dic = proc_dict[proc.pid]
        print(p_dic['name'], p_dic['pid'], p_dic['cpu_num'], str(end_time - p_dic['create_time']))

    psutil.wait_procs(p_list, timeout=None, callback=print_time)
    return

def run_on_cores_restart(process_info_list, copies=1, cores=None, rstrt_even=False):
    """ Take the output from parse_file and launch the processes on cores=[cpu,...] """
    # Ensure size of cores and process_info_list is same
    num_procs = len(process_info_list)
    if num_procs > 2:
        print("More than 2 processes")
        exit(1)
    # one more check for len(process_info_list) == len(cores)
    if cores is None:
        cores = range(copies)

    restarted = []
    p_list = []
    proc_dict = {}
    for cpu in cores:
        process_info = process_info_list[cpu % num_procs]
        p = launch_on_core(process_info, cpu)
        p_dict_loc = p.as_dict()
        p_dict_loc['work_info'] = process_info_list[cpu % num_procs]
        proc_dict[p_dict_loc['pid']] = p_dict_loc
        p_list.append(p)

    def print_time(proc):
        """ Print Process Info on compeletion """
        end_time = time()
        p_dic = proc_dict[proc.pid]
        print(p_dic['name'], p_dic['pid'], p_dic['cpu_num'], str(end_time - p_dic['create_time']))
        _p_rst = None
        if rstrt_even and p_dic['cpu_num']%2 == 0:
            _p_rst = Process(target=run_on_core_forever, args=(process_info_list[p_dic['cpu_num'] % num_procs], p_dic['cpu_num']))
            _p_rst.start()
            restarted.append(_p_rst)

    gone, alive = psutil.wait_procs(p_list, timeout=None, callback=print_time)
    for _p in alive:
        _p.kill()
    if len(restarted) >= 1:
        # kill all restrted processes
        for _proc in restarted:
            try:
                _proc.terminate()
            except:
                pass
    return

def run_on_multiple_cores_forever(process_info_list, cores=None):
    """ Take the output from parse_file and launch the processes on cores=[cpu,...] """
    # check if proc list is None
    if process_info_list is None:
        return
    # one more check for len(process_info_list) == len(cores)
    if cores is None:
        cores = [i*2 for i in range(len(process_info_list))]
    
    restarted = []
    for i, cpu in enumerate(cores):
        process_info = process_info_list[i]
        _p_rst = None
        _p_rst = Process(target=run_on_core_forever, args=(process_info, cpu))
        _p_rst.start()
        restarted.append(_p_rst)

    return
