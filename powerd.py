
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

from frequency import *
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

def change_freq(target_power, increase=False):
    # power differential to freq reduction factor
    new_freq = freq_at_power(target_power)
    old_freq = int(read_freq())
    # print(new_freq, old_freq, target_power)

    if abs(old_freq - new_freq) <= 1000:
        return

    new_power = power_at_freq(new_freq)

    if increase:
        while new_power < target_power:
            old_power = power_at_freq(new_freq)
            new_freq = new_freq + 100000
            new_power = power_at_freq(new_freq)
            if new_power == old_power:
                new_freq =  new_freq - 100000
                break
            # print(new_freq, old_freq, new_power, target_power)
    else:
        while new_power > target_power:
            old_power = power_at_freq(new_freq)
            new_freq = new_freq - 100000
            new_power = power_at_freq(new_freq)
            # print(new_freq, old_freq, new_power)
            if new_power == old_power:
                new_freq =  new_freq + 100000
                break

    # WARN: Hardecoded cpu numbers below
    for i in range(psutil.cpu_count()):
        write_freq(new_freq, i)

def keep_limit(curr_power, limit=20000, first_limit=True):
    new_limit = limit

    if not first_limit:
        if curr_power - limit > 0 and new_limit > 5000:
            new_limit = new_limit - abs(curr_power - new_limit)/4
            #new_limit = new_limit - 1000
        elif curr_power - limit < 0 and new_limit > 5000:
            new_limit = new_limit + abs(curr_power - new_limit)/4
            #new_limit = new_limit + 1000

    # print("In keep_limit ", limit)
    if curr_power > limit:
        # reduce frequency
        change_freq(new_limit)
    elif curr_power < limit:
        # print("Increase")
        change_freq(new_limit, increase=True)
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
        istat = getSysStats()
        istat['energy'] = _ea.get_update_energy()
        ostat = _sys_stats.update_stat(istat)
        # print(ostat['freqs'])
        print()
        keep_limit(curr_power, set_limit, first_limit)
        print(" ---- \n")
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
