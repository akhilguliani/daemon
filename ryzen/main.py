
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
import psutil
import matplotlib.pyplot as plt
import sys
from docopt import docopt
from schema import Schema, And, Or, Use, SchemaError
from topology import cpu_tree
from msr import AMD_MSR_CORE_ENERGY, writemsr, readmsr, get_percore_msr, get_percore_energy, get_units, setup_perf
from tracker import PerCoreTracker, update_delta, update_delta_32
from frequency import *
from launcher import *
from operator import itemgetter
from multiprocessing import Process

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
    i = 0
    retdict, retval = launch_all(list_proc)
    wait_for_procs(retval, post_exec_fn)
    return


def plot_all(freq_dict, pwr_dict, perf_dict, tick, cpus, pwr_limits):
    grid_size = len(cpus)
    c = ['m','b','g','k','m','b','g','k']
    ax = []
    for i in range(len(cpus)):
        if i == 0:
            ax.append(plt.subplot(3, grid_size, i+1))
        else:
            plt.subplot(3, grid_size, i+1, sharey=ax[0])
        plt.scatter(tick, freq_dict[cpus[i]], marker='.', color=c[i])
        plt.ylim(ymin=1000000, ymax=3600000)

        if i == 0:
            ax.append(plt.subplot(3, grid_size, i+1+len(cpus)))
        else:
            plt.subplot(3, grid_size, i+len(cpus)+1, sharey=ax[1])
        plt.axhline(y=pwr_limits[i], color='r', linestyle='-')
        plt.scatter(tick, pwr_dict[cpus[i]], marker='.', color=c[i])
        plt.ylim(ymin=0, ymax=12000)

        if i == 0:
            ax.append(plt.subplot(3, grid_size, i+(2*len(cpus))+1))
        else:
            plt.subplot(3, grid_size, i+(2*len(cpus))+1, sharey=ax[2])
        plt.scatter(tick, perf_dict[cpus[i]], marker='.', color=c[i])

        #plt.ylim(ymin=0)
    plt.draw()
    plt.pause(0.1)


def main(arg1, energy_unit, tree):
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

    perf_msr = 0xC00000E9
    # get cpu id's as a list
    cpus = [list(tree[0][i].keys())[0] for i in range(psutil.cpu_count(logical=False))]

    track_energy = PerCoreTracker(dict(zip(cpus, [0 for i in cpus])))
    track_perf = PerCoreTracker(dict(zip(cpus, [0 for i in cpus])))
    power_tracker = PerCoreTracker(dict(zip(cpus, [0 for i in cpus])))
    first = True
    old_freq = [None] * len(cpus)
    count = 0
    list_procs = parse_file(arg1['--input'])
    limit = 24
    max_per_core = 10
    list_procs.sort(key=itemgetter(3))
    high = [r for r in list_procs if r[3] < 0]
    total_shares = sum([r[2] for r in high])
    shares_per_app = [r[2]/total_shares for r in high]
    print(total_shares, shares_per_app)
    limits = [r*limit*1000 if r*limit < max_per_core else max_per_core*1000 for r in shares_per_app]
# Adjust limits so that excess power can overflow to the rest
#    shares_per_watt = [x[2]/y for x,y in zip(high, limits)]
    change = PerCoreTracker()
#    limits = [5000, 8000, 6000, 10000]
    wait_thread = Process(target=launch_all, args=(high,))
#    wait_thread = Process(target=launch_all_with_post_fn, args=(high, exit_when_done))
    wait_thread.start()

    while True:
        before = PerCoreTracker(dict(zip(cpus, get_percore_energy(cpus))))
        perf_before = PerCoreTracker(dict(zip(cpus, get_percore_msr(perf_msr, cpus))))
        sleep(int(arg1['--interval']))

        after = PerCoreTracker(dict(zip(cpus, get_percore_energy(cpus))))
        delta = update_delta_32(before, after)
        perf_after = PerCoreTracker(dict(zip(cpus, get_percore_msr(perf_msr, cpus))))

        track_energy = track_energy + delta.scalar_mul(energy_unit)

        perf_delta = update_delta(perf_before, perf_after)

        delta.scalar_mul(1000)

        ## Percent change
        if first:
            power_tracker = delta
            track_perf = perf_delta
        else:
            change = (abs(delta - power_tracker) / power_tracker).scalar_mul(100)
            power_tracker = (power_tracker).scalar_mul(0.7) + (delta).scalar_mul(0.3)
            track_perf = track_perf.scalar_mul(0.7) + perf_delta.scalar_mul(0.3)

        for i in range(4):
            #if change == {} or (change[cpus[i]] < 1 and delta[cpus[i]] < limits[i]):
            #    continue
            #if i == 0:
            #    continue
            old_freq[i] = keep_limit(power_tracker[cpus[i]], limits[i], cpus[i], old_freq[i], first)

        print(round(power_tracker, 3))
        # print(round(change, 3), "\n")
        # print(old_freq)
        f_dict = dict(zip(cpus, [read_freq_real(cpu=i) for i in cpus]))
        print(f_dict)
        print(round(perf_delta, 3), "\n________")

        first = False
        count = count + 1
        plot_all(f_dict, power_tracker, track_perf, count, cpus[:len(high)], limits)

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
    setup_perf()
    energy_unit = get_units()
    set_gov_userspace()
    set_to_max_freq()
    main(ARGUMENTS, energy_unit, tree)
