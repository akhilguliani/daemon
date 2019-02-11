
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

def getProcess(_pids=None):
    """
    Iterate over all process and print proc vals
    """
    p_dict = {}
    for pid in _pids:
        print(pid)
        _p = psutil.Process(pid)
        p_dict[pid] = _p.as_dict()
    # print(p_list)
    return p_dict

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
        if interval >= 1:
            return (self.energy-prev_energy)/(interval*self.MILLI)
        else:
            return (self.energy-prev_energy)/((interval*self.MILLI)*10)

    def get_diff(self,prev_energy):
        self.update()
        return self.energy - prev_energy

class Entity(Enum):
    """
    Tracked entity recognizer
    """
    System = 1
    Process = 2

class StatsTracker:
    """
    Stats base Class
    Used to track stats for an entity
    """
    stat = None
    entity = None

    def __init__(self, entity, i_stat):
        self.stat = {}
        self.entity = entity
        self.stat = i_stat
        ## get the right factor
        if self.entity == Entity.System:
            self.stat['factor'] = 1
        else:
            _t = i_stat['time']
            _st = getSysStats()['time']
            self.stat['factor'] = (_t[0]+_t[1])/_st[0]+_st[2]

    def update_stat(self,i_stat):
        for key in i_stat.keys():
            self.stat[key] = i_stat[key]
        ## get the right factor
        ## Only accounting for process time without children
        if self.entity != Entity.System:
            _t = i_stat['time']
            _st = getSysStats()['time']
            self.stat['factor'] = (_t[0]+_t[1])/_st[0]+_st[2]

        return self.stat

    def get_stat(self, item=None):
        if item != None:
            return self.stat[item]
        return self.stat

    def get_stat_diff(self, prev_stat,item=None):
        diff_stat = {}
        ## write stat_diff

        if item != None:
            if item == "time":
                diff_stat[item] = psutil._cpu_times_deltas(prev_stat[item], self.stat[item])
            return diff_stat[item]
        return self.stat


class ProcessTracker(StatsTracker):
    """
    extending the stats tracker to track a process
    """
    pid = None
    name = None
    core = None
    procstat = None

    def __init__(self, i_stat, p_stat):
        i_stat['time'] = p_stat['cpu_times']
        super().__init__(Entity.Process, i_stat)
        self.pid = p_stat['pid']
        self.name = p_stat['name']
        self.core = p_stat['cpu_num']
        self.procstat = p_stat

    def update(self, i_stat, p_stat):
        if self.name != p_stat['name']:
            return
        i_stat['time'] = p_stat['cpu_times']
        self.update_stat(i_stat)
        self.pid = p_stat['pid']
        self.name = p_stat['name']
        self.core = p_stat['cpu_num']
        self.procstat = p_stat

