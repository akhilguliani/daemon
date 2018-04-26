""" Main process loop for managing power
by Akhil Guliani

Usage:
    powerd.py [-hi FILE] [--timeout=<minutes>] PID...


Arguments:
    PID     pids to track


Options:
    -h --help
    -i FILE --input=FILE    file with pids to monitor and their control params
    --timeout=<minutes>   max amount of time in minutes to keep the daemon alive
"""

from docopt import docopt
from schema import Schema, And, Or, Use, SchemaError
import psutil
import subprocess



def main(arg1):
    """
    The main funtion loop.

    Parameters
    ----------
    arg1 : dict
        commandline arguments from
    """
    print(arg1)
    p_one = psutil.Process(1)
    print(p_one)

if __name__ == "__main__":
    # execute only if run as a script
    ARGUMENTS = docopt(__doc__, version="0.01a")

    SCHEMA = Schema({
        'PID': [Or(None, And(Use(int), lambda n: 1 < n < 32768),
                   error='PID should be inteager within 1 < N < 32768')],
        '--input': Or(None, And(Use(open, error='FILE should be readable'))),
        '--timeout': Or(None, And(Use(int), lambda n: 0 < n < 1000),
                        error='--timeout=N should be integer 0 < N < 1000')})
    try:
        ARGUMENTS = SCHEMA.validate(ARGUMENTS)
    except SchemaError as _e:
        exit(_e)

    # Start main program here
    main(ARGUMENTS)
