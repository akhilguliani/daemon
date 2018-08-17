
""" Main process loop for managing power
by Akhil Guliani

Usage:
    main.py [-i FILE] [--interval=<seconds>] [--limit=<watts>] [--cores=<num>] [--type=<Share_Type>] PID...

Arguments:
    PID     pids to track

Options:
    -h
    -i FILE --input=FILE    file with pids to monitor and their control params
    --interval=<seconds>   max amount of time in minutes to keep the daemon alive
    --limit=<watts>   combined core power limit
    --cores=<num>   number of active cores
    --type=<Share_type> type of shares power or frequency  
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
from msr import AMD_MSR_CORE_ENERGY, writemsr, readmsr, get_percore_msr, get_percore_energy, get_units, setup_perf, get_package_energy
from tracker import PerCoreTracker, update_delta, update_delta_32, update_pkg
from frequency import keep_limit_prop_freq, keep_limit, read_freq_real, set_gov_userspace, set_to_max_freq
from launcher import run_on_multiple_cores_forever, launch_on_core, wait_for_procs
from operator import itemgetter
from multiprocessing import Process
from shares import get_list_limits, get_list_limits_cores, get_new_limits

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
    package_tracker = 0

    sum_freq = PerCoreTracker(dict(zip(cpus, [0 for i in cpus])))
    sum_perf = PerCoreTracker(dict(zip(cpus, [0 for i in cpus])))
    sum_power = PerCoreTracker(dict(zip(cpus, [0 for i in cpus])))
    sum_package = 0

    first = True
    old_freq = [None] * len(cpus)
    count = 0
    proc_file = arg1['--input']
    power_limit = int(arg1['--limit'])
    cores = int(arg1['--cores'])
    option = arg1['--type']

    high_list, high_cores, low_list, low_cores, limits, high_limits, low_limits, high_shares, low_shares, shares = [None]*10
    
    if option == "power":
        # Power shares
        high_list, high_cores, low_list, low_cores, limits, high_limits, low_limits, high_shares, low_shares, shares = get_list_limits_cores(power_limit, cores, proc_file, opt="Power")
    elif option == "freq":
        # Frequency shares
        high_list, high_cores, low_list, low_cores, limits, high_limits, low_limits, high_shares, low_shares, shares = get_list_limits_cores(power_limit, cores, proc_file, opt="Freq")
    
    #wait_thread = Process(target = run_on_multiple_cores_forever, args=(proc_list, cpus))
    wait_high_threads = Process(target=run_on_multiple_cores_forever, args=(high_list, high_cores))
    wait_low_threads = Process(target=run_on_multiple_cores_forever, args=(low_list, low_cores))
    
    if low_list is None:
        print("Low", "None", "None")
    else:
        print("Low", len(low_list), low_cores, low_limits, low_shares)
    
    if high_list is None:
        print("High", "None", "None")
    else:
        print("High", len(high_list), high_cores, high_limits, high_shares)
    
    print("Limits", limits)

    print("Power Limit", power_limit)

    wait_high_threads.start()

    power_diff = 0

    control_start = len(high_cores)

    first_control = True
    lp_active = False
    run_lp = False

    while True:
        pwr_before = PerCoreTracker(dict(zip(cpus, get_percore_energy(cpus))))
        perf_before = PerCoreTracker(dict(zip(cpus, get_percore_msr(perf_msr, cpus))))
        package_before = get_package_energy()
        sleep(int(arg1['--interval']))

        pwr_after = PerCoreTracker(dict(zip(cpus, get_percore_energy(cpus))))
        perf_after = PerCoreTracker(dict(zip(cpus, get_percore_msr(perf_msr, cpus))))
        package_after = get_package_energy()

        power_delta = update_delta(pwr_before, pwr_after)
        track_energy = track_energy + power_delta.scalar_mul(energy_unit)
        power_delta.scalar_mul(1000)

        perf_delta = update_delta(perf_before, perf_after)
        package_pwr = update_pkg(package_before, package_after) * energy_unit * 1000

        ## Percent change
        if first:
            power_tracker = power_delta
            package_tracker = package_pwr
            track_perf = perf_delta
        else:
            # change = (abs(power_delta - power_tracker) / power_tracker).scalar_mul(100)
            package_tracker = package_tracker*0.7 + package_pwr*0.3
            power_tracker = (power_tracker).scalar_mul(0.7) + (power_delta).scalar_mul(0.3)
            track_perf = track_perf.scalar_mul(0.7) + perf_delta.scalar_mul(0.3)
        
        count = count + 1
        first = False
        f_dict = PerCoreTracker(dict(zip(cpus, [read_freq_real(cpu=i) for i in cpus])))

        if option == "power":
            if count < 5:
                pass
            elif count > 5 and count < 30 :
                for i in range(len(high_cores)):
                    if i == 0:
                        old_freq[i] = keep_limit(power_tracker[cpus[i]], limits[i], cpus[i], old_freq[i], first_limit=first_control, leader=True)
                    else:
                        #old_freq[i] = keep_limit(power_tracker[cpus[i]], limits[i], cpus[i], old_freq[i], False)
                        old_freq[i] = keep_limit(power_tracker[cpus[i]], limits[i], cpus[i], old_freq[i], first_limit=first_control)
                first_control = False
                base = count
            elif count > 30:
                # check if we have enough power for low priority
                current_power   = sum([power_tracker[i*2] for i in range(cores)])
                if first and not (low_cores is None):
                    print("RUNNIG LOW", power_limit*1000 - current_power,( power_limit - current_power > 1*1000*len(low_cores)) )
                    if power_limit*1000 - current_power  > 1000*len(low_cores):
                        # we have excess power at a steady enough state for Low Priority
                        excess = abs(power_limit*1000 - current_power)
                        limits = get_new_limits(shares, control_start, excess, limits, cores)
                        print("New Limits", limits)
                        wait_low_threads.start()
                        control_start = len(high_cores)+len(low_cores)
                        lp_active = True
                
                if count % 40 == 0:
                    # Unused Power redistribution hack (ony for proporional share) comment out for priority runs
                    if power_limit*1000 - current_power  > 2000:
                        # print("Have excess_Power")
                        # we have more than two watss to distribute
                        # we increase limts for all (will have no effect on programs already at highest p_state)
                        excess = abs(power_limit*1000 - current_power)
                        limits = get_new_limits(shares, 0, excess, limits, cores, freqs=list(f_dict.values()))

                for i in range(control_start):
                    if lp_active:
                        leader_conditon = (i == 0 or i == len(high_cores))
                    else:
                        leader_conditon = (i == 0 or i == 4)

                    # print(leader_conditon, lp_active)
                    if leader_conditon:
                        old_freq[i] = keep_limit(power_tracker[cpus[i]], limits[i], cpus[i], old_freq[i], first_limit=False, leader=True)
                    else:
                        old_freq[i] = keep_limit(power_tracker[cpus[i]], limits[i], cpus[i], old_freq[i], False)

                sum_perf = sum_perf + perf_delta
                sum_freq = sum_freq + f_dict
                sum_power = sum_power + power_tracker
                sum_package = sum_package + package_pwr
        
        elif option == "freq":

            if count > 5 and count < 30 :
                run_lp, high_limits, low_limits = keep_limit_prop_freq(package_tracker, power_limit*1000, high_limits, low_limits, 
                                                                       high_shares, low_shares, high_cores, low_cores, 
                                                                       first_limit=first_control, lp_active=False)
                first_control = False
                base = count
            elif count > 30:
                # check if we have enough power for low priority
                # current_power   = sum([power_tracker[i*2] for i in range(cores)])
                current_power = package_tracker
                if first and not (low_cores is None):
                    print("RUNNIG LOW: ", power_limit*1000 - current_power,( power_limit*1000 - current_power > 1000*len(low_cores)) )
                    if power_limit*1000 - current_power  > 1000*len(low_cores) and run_lp:
                        # we have excess power at a steady enough state for Low Priority
                        excess = abs(power_limit*1000 - current_power)
                        # low_limits = get_new_limits(low_shares, 0, excess, low_limits, low_cores, alpha=(excess/95000))
                        # print("New low Limits", low_limits)
                        wait_low_threads.start()
                        lp_active = True
                    first = False

                run_lp, high_limits, low_limits = keep_limit_prop_freq(package_tracker, power_limit*1000, high_limits, low_limits, 
                            high_shares, low_shares, high_cores, low_cores, 
                            first_limit=first_control, lp_active=lp_active)

                sum_perf = sum_perf + perf_delta
                sum_freq = sum_freq + f_dict
                sum_power = sum_power + power_tracker
                sum_package = sum_package + package_pwr


        if count > 30:    
            print(package_tracker)
            print(round(sum_power.scalar_div(count-base), 0))
            print(round(sum_freq.scalar_div(count-base), 0))
            print(round(sum_perf.scalar_div(count-base), 0))
            
            power_diff += (power_limit*1000) - current_power

            print(count, current_power, int(power_diff/(count-base)), int(sum_package/(count-base)), package_tracker,sep=", ")

        print("\n---------------")
        print(package_tracker)
        print(round(power_tracker, 3))
        print(f_dict)
        print(round(perf_delta, 3), "\n________")
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
        '--limit': Or(None, And(Use(int), lambda n: 0 < n < 95),
            error='--limit=N should be integer 0 < N < 95'),
        '--cores': Or(None, And(Use(int), lambda n: 2 < n < 9),
            error='--cores=N should be integer 3 <= N <= 8'),
        '--type': Or(None, And(str, Use(str.lower), lambda n: n in ("power", "freq")),
            error='--type=power|freq Select share type'),
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
