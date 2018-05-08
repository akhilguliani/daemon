
"""
Helper Classes and functions
Author Akhil Guliani
"""
import psutil
import subprocess
import time

from enum import Enum

#### Functions

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

### Classes

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
        self.energy = self.get_update_energy()
        if share > 0 and share < 100:
            self.share = share
        else:
            self.share = 0
        self.author = "Akhil Guliani"
        self.description = "Lets track some energy shall we"

    def get_update_energy(self):
        # domain = 0
        energy_file = open(self.energy_loc+"energy_uj", 'r')
        energy = int(energy_file.read())
        if energy < self.energy:
            self.energy = energy + self.MAX_ENERGY
        else:
            self.energy = energy
        energy_file.close()
        return self.energy

    def update(self):
        # domain = 0
        energy_file = open(self.energy_loc+"energy_uj", 'r')
        energy = int(energy_file.read())
        if energy < self.energy:
            self.energy = energy + self.MAX_ENERGY
        else:
            self.energy = energy
        energy_file.close()

    def get_energy(self):
        return self.energy

    def get_power(self,prev_energy, interval=1):
        """
        return power in milli watts after interval
        """
        # ensure latest value is updated
        self.update()
        # return power value in milliwats
        return (self.energy-prev_energy)/(interval*self.MILLI)

class Entity(Enum):
    System = 1
    Process = 2

class StatsTracker:
    """
    Stats base Class
    Used to track stats for an entity
    """
    stat = None
    entity = None

    def __init__(self, entity, i_time, i_freq, i_temp, i_energy):
        self.stat = {}
        self.entity = entity
        self.stat['time'] = i_time
        self.stat['temp'] = i_temp
        ## get the right factor
        if self.entity == Entity.System:
            self.stat['factor'] == 1
        else:
            self.stat['factor'] = (i_time[0]+i_time[1])/(getSysStats()['time'][0]+getSysStats()['time'][2])
        self.stat['energy'] = i_energy

    def update_stat(self,i_time,i_freq,i_temp,i_energy):
        self.stat['time'] = i_time
        self.stat['temp'] = i_temp
        ## get the right factor
        ## Only accounting for process time without children
        if self.entity != Entity.System:
            self.stat['factor'] = (i_time[0]+i_time[1])/(getSysStats()['time'][0]+getSysStats()['time'][2])
        self.stat['energy'] = i_energy

    def get_stat(self, item=None):
        if item != None:
            return self.stat[item]
        return self.stat

    def get_stat_diff(self, prev_stat,item=None):
        diff_stat = {}


        if item != None:
            return diff_stat[item]
        return self.stat



class ProcessTracker(StatsTracker):
    """
    extending the stats tracker to track a process
    """
    _pid = None
    _name = None
    _affinity = None
    _priority = None

    def __init__(self, i_stat, p_stat):
        super().__init__(Entity.Process, p_stat['cpu_times'], i_stat['freq'],
                         i_stat['temp'], i_stat['energy'])
        self._pid = p_stat['pid']
        self._name = p_stat['name']
        self._affinity = p_stat['cpu_affinity']
        self._priority = p_stat['nice']

    def update(self, i_stat, p_stat):
        self.update_stat(p_stat['cpu_times'], i_stat['freq'], i_stat['temp'],
                         i_stat['energy'])
        self._pid = p_stat['pid']
        self._name = p_stat['name']
        self._affinity = p_stat['cpu_affinity']
        self._priority = p_stat['nice']

