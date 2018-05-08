
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
import time
import signal
import sys
from helper import *


def signal_handler(signal, frame):
    print('\nExiting Daemon')
    # Do cleanup in the future
    sys.exit(0)


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
    _ea = EnergyTracker(100)

    while 1:
        prev_energy = _ea.get_update_energy()
        time.sleep(int(arg1['--interval']))
        #eA.updateEnergy()
        print(_ea.get_power(prev_energy, int(arg1['--interval'])))
        print(getSysStats(0))


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
