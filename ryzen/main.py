
""" Main process loop for managing power
by Akhil Guliani

Usage:
    main.py [-i FILE] [--interval=<seconds>] PID...

Arguments:
    PID     pids to track

Options:
    -h
    -i FILE --input=FILE    file with pids to monitor and their control params
    --interval=<seconds>   max amount of time in minutes to keep the daemon alive
"""

import os
import signal
import subprocess
from time import sleep
from multiprocessing import Process
import shlex
import psutil
import matplotlib.pyplot as plt
from docopt import docopt
from schema import Schema, And, Or, Use, SchemaError
from topology import cpu_tree
# from msr import writemsr, readmsr, get_percore_msr
from tracker import PerCoreTracker
from frequency import *
from launcher import run_on_multiple_cores_forever, launch_on_core, wait_for_procs
from helper import EnergyTracker
from shares import get_list_limits

def signal_handler(_signal, _frame):
    """ Handle SIGINT"""
    print("\nExiting ...")
    plt.show()
    exit(0)

def check_for_sudo_and_msr():
    """ Check if we are root and have the msr driver loaded in"""
    if os.geteuid() != 0:
        raise OSError("Need sudo to run")
    else:
        # ensure modprobe msr is run
        subprocess.run(["modprobe", "msr"])

def setup_perf():
    perf_dir = "/mydata/linux-4.17.8/tools/perf"
    perf_args = shlex.split("./perf stat -I 1000 -e instructions -A -x ,")
    return subprocess.Popen(perf_args, stderr=subprocess.PIPE, cwd=perf_dir, universal_newlines=True)

def get_perf(perf_obj, num_cores):
    ret = [int(perf_obj.stderr.readline().strip().split(",")[2]) for i in range(psutil.cpu_count())]
    return ret[:num_cores]

def launch_all(list_proc):
    """Launch all the process in the list on successive cores"""
    i = 0
    retval = []
    retdict = {}
    for proc in list_proc:
        _p = launch_on_core(proc, cpu=i*2)
        retval.append(_p)
        retdict.update({i*2:_p.as_dict()})
        i = i+1
    return retdict, retval

def exit_when_done(procs):
    """Post execution function for static executions"""
    print("\nExiting ...")
    os.killpg(os.getpgrp(), signal.SIGINT)
    # plt.show()
    exit(0)


def launch_all_with_post_fn(list_proc, post_exec_fn):
    """Launch all the process in the list on successive cores"""
    retdict, retval = launch_all(list_proc)
    wait_for_procs(retval, post_exec_fn)
    return

def plot_all(freq_dict, pwr_dict, perf_dict, tick, cpus, pwr_limits):
    """ Function For Observing Dynamic behaviour of the system"""
    grid_size = len(cpus)
    c = ['m','b','g','k','m','b','g','k']
    ax = []
    for i in range(len(cpus)):
        if i == 0:
            ax.append(plt.subplot(3, grid_size, i+1))
        else:
            plt.subplot(3, grid_size, i+1, sharey=ax[0])
        plt.scatter(tick, freq_dict[cpus[i]], marker='.', color=c[i])
        plt.ylim(ymin=500000, ymax=3800000)

        if i == 0:
            ax.append(plt.subplot(3, grid_size, i+1+len(cpus)))
        else:
            plt.subplot(3, grid_size, i+len(cpus)+1, sharey=ax[1])
        plt.axhline(y=pwr_limits[i], color='r', linestyle='-')
        plt.scatter(tick, pwr_dict[cpus[i]], marker='.', color=c[i])
        plt.ylim(ymin=0, ymax=14000)

        if i == 0:
            ax.append(plt.subplot(3, grid_size, i+(2*len(cpus))+1))
        else:
            plt.subplot(3, grid_size, i+(2*len(cpus))+1, sharey=ax[2])
        plt.scatter(tick, perf_dict[cpus[i]], marker='.', color=c[i])
        plt.ylim(ymin=1e9, ymax=10e9)

        #plt.ylim(ymin=0)
    plt.draw()
    plt.pause(0.1)
    return


def main(arg1, perf_file, tree):
    """
    Main funtion loop.

    Parameters
    ----------
    arg1 : dict
        commandline arguments as a dictionary
    energy_unit : int
        Multiplication factor for energy measurements
    tree : Dict
        CPU topology tree
   """

    # get cpu id's as a list # topolgy function not parsing for intel
    #TODO: replace hard code later
    cpus = range(int(psutil.cpu_count(logical=False)/2))
    print(cpus)

    track_energy = EnergyTracker(100)
    track_perf = PerCoreTracker(dict(zip(cpus, [0 for i in cpus])))
    power_tracker = 0

    sum_freq = PerCoreTracker(dict(zip(cpus, [0 for i in cpus])))
    sum_perf = PerCoreTracker(dict(zip(cpus, [0 for i in cpus])))
    sum_power = 0

    first = True
    old_freq = [None] * len(cpus)
    count = 0
    proc_file = arg1['--input']
    power_limit = 25
    cores = 4
    max_per_core = 10000
    proc_list, limits = get_list_limits(power_limit, cores, proc_file)

    if limits is None:
        limits = [max_per_core]*cores
    else:
        cores = len(limits)

    wait_thread = Process(target=run_on_multiple_cores_forever, args=(proc_list, cpus[:cores]))

    # change = PerCoreTracker()
#    limits = [5000, 8000, 6000, 10000]
#    wait_thread = Process(target=launch_all, args=(high,))

#    wait_thread = Process(target=launch_all_with_post_fn, args=(high, exit_when_done))
    wait_thread.start()

    interval = int(arg1['--interval'])
    while True:

        prev_energy = track_energy.get_update_energy()

        sleep(interval)

        perf_delta = PerCoreTracker(dict(zip(cpus, get_perf(perf_file,len(cpus)))))
        package_pwr = track_energy.get_power(prev_energy, interval)
        ## Percent change
        if first:
            power_tracker = package_pwr
            track_perf = perf_delta
        else:
            # change = (abs(power_delta - power_tracker) / power_tracker).scalar_mul(100)
            power_tracker = (power_tracker)*(0.7) + (package_pwr)*(0.3)
            track_perf = track_perf.scalar_mul(0.7) + perf_delta.scalar_mul(0.3)

        for i in range(cores):
            pass
            ## Write a new controller that takes in shares and power -> affects frequency
            # for Mixed priorities this controller also takes in core priorities with shares
            ### Lower Priority gets throttled to minimum till:
            ############# RAPL Limit Starts to drop
            ############# Or We have reached the lowest frequency (here we can start using DC to go lower)
            #### At lowest freq we should check how much HP is throttled, if below a threshold, then starve LP
            ## With Shares when we have to throttle the HP cores we do bin packing (Freq Shares we do 22 rounds for 22 levels)
            ###### At each level if the shares of the cores lie within threshold, we reduce their freq by one step starting from current
            ###### We also reduce the shares by the threshold delta (this way all apps get throttled eventually, and proportionally)
            ######## We continue with this trend till the power drops below limit or we reach
            # old_freq[i] = keep_limit(power_tracker[cpus[i]], limits[i], cpus[i], old_freq[i], first)
        count = count + 1

        f_dict = PerCoreTracker(dict(zip(cpus, [read_freq_real(cpu=i) for i in cpus])))
        sum_perf = sum_perf + perf_delta
        sum_freq = sum_freq + f_dict
        sum_power = sum_power + power_tracker

        print(round(sum_power/(count), 0))
        print(round(sum_freq.scalar_div(count), 0))
        print(round(sum_perf.scalar_div(count), 0))
        print(count, (power_limit*1000) - round(sum_power/count, 2), package_pwr, sep=", ")

        print("---------------")
        # print(round(power_tracker, 3))
        # print(f_dict)
        # print(round(perf_delta, 3), "\n________")

        first = False
        # plot_all(f_dict, power_tracker, track_perf, count, cpus[:len(limits)], limits)

## Starting point
if __name__ == "__main__":
    # Get Command line arguments
    ARGUMENTS = docopt(__doc__, version="0.01a")

    # Check Command line arguments
    SCHEMA = Schema({
        '--input': Or(None, And(Use(open,
            error='input FILE should be readable'))),
        '--interval': Or(None, And(Use(int), lambda n: 0 < n < 1000),
            error='--interval=N should be integer 0 < N < 1000'),
        'PID': [Or(None, And(Use(int), lambda n: 1 < n < 32768),
            error='PID should be inteager within 1 < N < 32768')],
        })
    try:
        ARG_VALIDATE = SCHEMA.validate(ARGUMENTS)
    except SchemaError as _e:
        exit(_e)

    signal.signal(signal.SIGINT, signal_handler)
    check_for_sudo_and_msr()
    # get cpu topology
    tree = cpu_tree()
    perf_file = setup_perf()
    set_gov_userspace()
    set_to_max_freq()
    main(ARGUMENTS, perf_file, tree)
