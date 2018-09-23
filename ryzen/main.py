
""" Main process loop for managing power
by Akhil Guliani

Usage:
    main.py [-i FILE] [--interval=<seconds>] [--limit=<watts>] [--cores=<num>] [-r BOOL] [-c BOOL] PID...

Arguments:
    PID     pids to track

Options:
    -h
    -i FILE --input=FILE    file with pids to monitor and their control params
    --interval=<seconds>   max amount of time in minutes to keep the daemon alive
    --limit=<watts>   RAPL limit
    --cores=<num>   Number of cores
    -r --rapl=BOOL
    -c --control=BOOL
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
from frequency import keep_limit_prop_freq, keep_limit_priority, read_freq_real, set_gov_userspace, set_to_max_freq, setup_rapl, set_rapl_limit
from launcher import run_on_multiple_cores_forever, launch_on_core, wait_for_procs
from helper import EnergyTracker
from shares import get_list_limits, get_lists, get_list_limits_cores

def signal_handler(_signal, _frame):
    """ Handle SIGINT"""
    print("\nExiting ...")
    #plt.show()
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
    sum_diff = 0

    first = True
    old_freq = [None] * len(cpus)
    count = 0
    proc_file = arg1['--input']
    rapl_limit = int(arg1['--limit'])
    power_limit = rapl_limit*1000
    cores = int(arg1['--cores'])
    use_rapl = eval(arg1['--rapl']) 
    use_control = eval(arg1['--control']) 
    print("RAPL: ", use_rapl, " - with controller: ", use_control)
    # max_per_core = 10000
    # proc_list, limits = get_list_limits(power_limit, cores, proc_file)

    # high_list, high_cores, low_list, low_cores = get_lists(power_limit, cores, proc_file)
    high_list, high_cores, low_list, low_cores, all_freqs, hi_freqs, low_freqs, hi_shares, low_shares = get_list_limits_cores(power_limit, cores, proc_file, opt="Freq")
    
    if low_list is None:
        print("Low", "None", "None")
    else:
        print("Low", len(low_list), low_cores)
    
    if high_list is None:
        print("High", "None", "None")
    else:
        print("High", len(high_list), high_cores)

    # if limits is None:
    #     limits = [max_per_core]*cores
    # else:
    #     cores = len(limits)

    wait_high_threads = Process(target=run_on_multiple_cores_forever, args=(high_list, high_cores))
    wait_low_threads = Process(target=run_on_multiple_cores_forever, args=(low_list, low_cores))
    # change = PerCoreTracker()
#    limits = [5000, 8000, 6000, 10000]
#    wait_thread = Process(target=launch_all, args=(high,))

#    wait_thread = Process(target=launch_all_with_post_fn, args=(high, exit_when_done))
    wait_high_threads.start()
    run_lp = False
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

        count = count + 1
        # for i in range(cores):
        #     pass
        if use_rapl:
            if first:
                print("Using RAPL: ", use_rapl)
                wait_low_threads.start()
                set_rapl_limit(rapl_limit)            
                base = 10
            elif use_control:
                # run_lp, hi_freqs, low_freqs = keep_limit_prop_freq(power_tracker, power_limit, hi_freqs, low_freqs, 
                #                                    hi_shares, low_shares, high_cores, low_cores, first_limit=False, lp_active=False)
                run_lp = keep_limit_priority(power_tracker, power_limit, high_cores, low_cores, first_limit=True, lp_active=run_lp)
        elif not use_rapl:
            # print("Our control Loop")
            if count < 10:
                # run_lp, hi_freqs, low_freqs = keep_limit_prop_freq(power_tracker, power_limit, hi_freqs, low_freqs, 
                #                                                    hi_shares, low_shares, high_cores, low_cores, first_limit=True, lp_active=False)
                run_lp = keep_limit_priority(power_tracker, power_limit, high_cores, low_cores, first_limit=True, lp_active=run_lp)
            if count == 10:
                ## High Prio Apps Ramped up
                run_lp = keep_limit_priority(power_tracker, power_limit, high_cores, low_cores, first_limit=True, lp_active=run_lp)
                # run_lp, hi_freqs, low_freqs = keep_limit_prop_freq(power_tracker, power_limit, hi_freqs, low_freqs, 
                #                                                   hi_shares, low_shares, high_cores, low_cores, first_limit=True, lp_active=False)
                print("RUNNING LOW PRIO", run_lp)
                if run_lp:
                    wait_low_threads.start()
                base = count
            elif count > 10:
                keep_limit_priority(power_tracker, power_limit, high_cores, low_cores, first_limit=False, lp_active=run_lp)
                # _, hi_freqs, low_freqs = keep_limit_prop_freq(power_tracker, power_limit, hi_freqs, low_freqs, 
                #                                               hi_shares, low_shares, high_cores, low_cores, first_limit=False, lp_active=run_lp)
               
        f_dict = PerCoreTracker(dict(zip(cpus, [read_freq_real(cpu=i) for i in cpus])))
        
        if count > 10:
        
            sum_perf = sum_perf + track_perf
            sum_freq = sum_freq + f_dict
            sum_power = sum_power + power_tracker
            sum_diff = sum_diff + (power_limit - power_tracker)

            print(round(sum_power/(count-base), 0))
            print(round(sum_freq.scalar_div(count-base), 0))
            print(round(sum_perf.scalar_div(count-base), 0))
            print(count, power_limit , sum_diff/(count-base), power_tracker, sep=", ")

        print("---------------")
        
        print(round(power_tracker, 3))
        print(f_dict)
        print(round(perf_delta, 3), "\n________")

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
        '--limit': Or(None, And(Use(int), lambda n: 25 < n < 86),
                      error='--limit=N should be integer 30 < limit < 85'),
        '--cores': Or(None, And(Use(int), lambda n: 0 < n < 11),
                      error='--cores=N should be integer 0 < num < 11'),
        '--rapl': Or(None, And(Use(eval), lambda n: n or True),
                      error='--rapl=True|False'),
        '--control': Or(None, And(Use(eval), lambda n: n or True),
                    error='--control=True|False'),
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
    setup_rapl()
    set_rapl_limit(85)
    main(ARGUMENTS, perf_file, tree)
