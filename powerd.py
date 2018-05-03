
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

from docopt import docopt
from schema import Schema, And, Or, Use, SchemaError
import psutil
import subprocess


# Create a class for holding historic values to get differences
# between intervals
MAX_ENERGY = 262143328850

def getEnergy(prev_energy, init=False):
    # Currenly using linux sysfs powercap interface to gather values
    # for AMD that might mean adating the powercap driver (TODO)
    # Can be substitued with MSR interface (Kernel Docs suggest to avoid)
    socket = 0
    domain = 0
    energy_loc = "/sys/devices/virtual/powercap/intel-rapl/intel-rapl:"+str(socket)+"/"
    energy_file = open(energy_loc+"energy_uj", 'r')
    if init == True:
        max_enrgy_file = open(energy_loc+"max_energy_range_uj", 'r')
        MAX_ENERGY = int(max_enrgy_file.read())
        max_enrgy_file.close()
    energy = int(energy_file.read())
    if energy < prev_energy:
        return energy + MAX_ENERGY
    else:
        return energy

def getSysStats(cpu=None):
    """
    Get system stats current value
    """
    # get cputimes

    # get temperatures

    # get frequencies

    # get energy
    ## attribute energy to a core
    energy = getEnergy(0,True)

    if cpu != None:
        # collect stats for particular cpu and return
        return 0
    else:
        # return everything
        return energy


def printProcess(_pids=['1']):
    """
    Iterate over all process and print proc vals
    """
    for pid in _pids:
        print(pid)
        _p = psutil.Process(int(pid))
        print(_p.as_dict())

def main(arg1):
    """
    The main funtion loop.

    Parameters
    ----------
    arg1 : dict
        commandline arguments from
    """
    print(arg1)
    printProcess(arg1['PID'])
    print(getSysStats())

if __name__ == "__main__":
    # execute only if run as a script
    ARGUMENTS = docopt(__doc__, version="0.01a")

    SCHEMA = Schema({
        '--input': Or(None, And(Use(open,
                      error='input FILE should be readable'))),
        '--interval': Or(None, And(Use(int), lambda n: 0 < n < 1000),
                        error='--interval=N should be integer 0 < N < 1000'),
         'PID': [Or(None, And(Use(int), lambda n: 1 < n < 32768),
                   error='PID should be inteager within 1 < N < 32768')],
         })
    try:
        arg_validator = SCHEMA.validate(ARGUMENTS)
    except SchemaError as _e:
        exit(_e)

    # Start main program here
    main(ARGUMENTS)
