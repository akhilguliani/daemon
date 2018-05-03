
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
import time
import signal
import sys

def signal_handler(signal, frame):
    print('\nExiting Daemon')
    # Do cleanup in the future
    sys.exit(0)

# Create a class for holding historic values to get differences
# between intervals
class EnergyTracker:
    """
    Class energyTracker
    Class designed to track the energy numbers provided by the powercap
    kernel interface, currently only usable for intel RAPL
    TODO extend the driver for use with AMD Ryzen, atleast the reporting api
    """

    MILLI = 1000
    MAX_ENERGY = 262143328850
    socket = 0
    energy = 0
    share = 0
    energy_loc = "/sys/devices/virtual/powercap/intel-rapl/intel-rapl:"+str(socket)+"/"

    def __init__(self, share):
        max_enrgy_file = open(self.energy_loc+"max_energy_range_uj", 'r')
        self.MAX_ENERGY = int(max_enrgy_file.read())
        max_enrgy_file.close()
        self.energy = self.getUpdateEnergy()
        if share > 0 and share < 100:
            self.share = share
        else:
            self.share = 0
        self.author = "Akhil Guliani"
        self.description = "Lets track some energy shall we"

    def getUpdateEnergy(self):
        # domain = 0
        energy_file = open(self.energy_loc+"energy_uj", 'r')
        energy = int(energy_file.read())
        if energy < self.energy:
            self.energy = energy + self.MAX_ENERGY
        else:
            self.energy = energy
        energy_file.close()
        return self.energy

    def updateEnergy(self):
        # domain = 0
        energy_file = open(self.energy_loc+"energy_uj", 'r')
        energy = int(energy_file.read())
        if energy < self.energy:
            self.energy = energy + self.MAX_ENERGY
        else:
            self.energy = energy
        energy_file.close()

    def getEnergy(self,share=100):
        return self.energy

    def getPower(self,prev_energy,interval=1):
        """
        return power in milli watts after interval
        """
        # ensure latest value is updated
        self.updateEnergy()
        # return power value in milliwats
        return (self.energy-prev_energy)/(interval*self.MILLI)


def getSysStats(cpu=None):
    """
    Get system stats current value
    get global values or values for one cpu
    """
    sys_stats = {}
    # get cputimes
    sys_stats['time'] = psutil.cpu_times()
    sys_stats['times'] = psutil.cpu_times(percpu=True)
    # get temperatures
    sys_stats['temps'] = (psutil.sensors_temperatures())['coretemp']
    # get frequencies
    sys_stats['freqs'] = psutil.cpu_freq(percpu=True)

    if cpu != None:
        # collect stats for particular cpu and return
        cpu_stats = {}
        cpu_stats['times'] = sys_stats['times'][cpu]
        cpu_stats['freqs'] = sys_stats['freqs'][cpu]
        cpu_stats['temps'] = sys_stats['temps'][cpu+1]
        cpu_stats['time'] = sys_stats['time']
        return cpu_stats
    # return everything
    return sys_stats


def printProcess(_pids=None):
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
    _ea = EnergyTracker(100)

    while 1:
        prev_energy = _ea.getUpdateEnergy()
        time.sleep(int(arg1['--interval']))
        #eA.updateEnergy()
        print(_ea.getPower(prev_energy, int(arg1['--interval'])))
        print(getSysStats(0))

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
