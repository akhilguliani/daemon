""" Helper functions to parse and launch programs presented in an input file """

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
                if theline=="High":
                    prio = -19
                elif theline=="Medium":
                    prio = 0
                elif theline=="Low":
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
