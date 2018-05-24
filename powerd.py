
""" Main process loop for managing power
by Akhil Guliani

Usage:
    powerd.py [-i FILE] [--interval=<minutes>] PID...

Arguments:
    PID     pids to track

Options:
    -h
    -i FILE --input=FILE    file with pids to monitor and their control params
    --interval=<seconds>   max amount of time in minutes to keep the daemon alive
"""

import time
import signal
import sys
from docopt import docopt
from schema import Schema, And, Or, Use, SchemaError

from helper import *

def signal_handler(signal, frame):
    """ SIGINT Handler for gracefull exit"""
    print('\nExiting Daemon')
    # Do cleanup in the future
    sys.exit(0)

def init_proc_tracker(_pids, i_stat):
    """
    Iterate over all process and setup proc_tracker
    """
    if _pids == None:
        return None
    p_dict = {}
    for pid in _pids:
        print(pid)
        _p = psutil.Process(pid)
        p_dict[pid] = ProcessTracker(i_stat, _p.as_dict())
    return p_dict

def print_tracker(p_dict):
    for key in p_dict.keys():
        print(p_dict[key].entity)
        print(p_dict[key].stat)
        print(p_dict[key].procstat)
        print("\n********\n")

def get_freq_bounds():
    bounds = [0, 0]
    freq_file = open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq", 'r')
    bounds[1] = int(freq_file.read())
    freq_file.close()
    freq_file = open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq", 'r')
    bounds[0] = int(freq_file.read())
    freq_file.close()
    return bounds

def set_gov_userspace():
    # Add check for intel_cpufreq
    driver_file = open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver")
    driver = driver_file.read()
    driver_file.close()

    if "cpufreq" in driver:
        for i in range(psutil.cpu_count()):
            gov_file = "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_governor" % i
            gfd = open(gov_file, 'w')
            gfd.write("userspace")
            gfd.close()
    else:
        print("Unspported Driver: please enable intel/acpi_cpufreq from kerenl cmdline")

def read_freq(cpu=0):
    f_file = "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_cur_freq" % cpu
    freq_file = open(f_file)
    ret_val = freq_file.read()
    freq_file.close()
    return ret_val

def write_freq(val, cpu=0):
    bounds = get_freq_bounds()
    if val <= bounds[1] and val >= bounds[0]:
        print("Changing Freq to ", str(val))
        f_file = "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_setspeed" % cpu
        freq_file = open(f_file, 'w')
        freq_file.write(str(val))
        freq_file.close()
    return

def power_at_freq(freq):
    # freq is represented as 8 = 800MHz; 42 = 4200MHz
    return (0.0211*((freq/100000)**2) - (0.4697)*(freq/100000)+ 7.7535)*1000

def freq_at_power(power):
    return int(-0.0773*((power/1000)**2)+ 3.7436*(power/1000) - 4.6404)*100000

def reduce_freq(target_power):
    # power differential to freq reduction factor
    new_freq = freq_at_power(target_power)
    old_freq = int(read_freq())

    if old_freq - new_freq <= 100:
        return

    new_power = power_at_freq(new_freq)
    while(new_power > target_power):
        new_freq = new_freq - 100000
        new_power = power_at_freq(new_freq)
        print(new_freq, old_freq, new_power)
    # WARN: Hardecoded cpu numbers below
    for i in range(psutil.cpu_count()):
        write_freq(new_freq, i)

def keep_limit(curr_power, limit=20000):
    # check current
    if curr_power > limit:
        # reduce frequency
        reduce_freq(limit)
    return

def main(arg1):
    """
    The main funtion loop.

    Parameters
    ----------
    arg1 : dict
        commandline arguments from
    """
    print(arg1)
    pids = list(map(int, arg1['PID']))
    _ea = EnergyTracker(100)
    istat = getSysStats()
    istat['energy'] = _ea.get_update_energy()
    _sys_stats = StatsTracker(Entity.System, istat)
    proc_dict = init_proc_tracker(pids, istat)
    print_tracker(proc_dict)

    set_gov_userspace()

    interval = int(arg1['--interval'])
    set_limit = 20000
    first_limit = True
    prev_energy = _ea.get_update_energy()
    time.sleep(interval)

    while 1:
        curr_power = _ea.get_power(prev_energy, interval)
        print(curr_power)
#        if not first_limit:
#            if curr_power > set_limit:
#                set_limit = set_limit - abs(curr_power - set_limit)
        istat = getSysStats()
        istat['energy'] = _ea.get_update_energy()
        ostat = _sys_stats.update_stat(istat)
        print(ostat['freqs'])
        print()
        keep_limit(curr_power, set_limit)
        first_limit = False
        prev_energy = _ea.get_update_energy()
        time.sleep(interval)

##########################
#### Script Startup Code
##########################

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

    #Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)

    # Start main program here
    main(ARGUMENTS)
