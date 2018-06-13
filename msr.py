
import struct
import os
import glob
import signal
import subprocess
from time import sleep
import psutil
from topology import cpu_tree

AMD_MSR_PWR_UNIT =  0xC0010299
AMD_MSR_CORE_ENERGY = 0xC001029A
AMD_MSR_PACKAGE_ENERGY = 0xC001029B

class PerCoreTracker(dict):
    """
    Class for tracking percore energy values
    """
    def __add__(self, other):
        rv = PerCoreTracker()
        for key, value in self.items():
            if key in other.keys():
                rv[key] = value + other[key]
        return rv

    def __sub__(self, other):
        rv = PerCoreTracker()
        for key, value in self.items():
            if key in other.keys():
                rv[key] = value - other[key]
        return rv

    def __lt__(self, other):
        rv = PerCoreTracker()
        ret = True
        for key, value in self.items():
            if key in other.keys():
                rv[key] = value < other[key]
                ret = rv[key] or ret
        return ret, rv

    def __le__(self, other):
        rv = PerCoreTracker()
        ret = True
        for key, value in self.items():
            if key in other.keys():
                rv[key] = value <= other[key]
                ret = rv[key] or ret
        return ret, rv

    def __eq__(self, other):
        rv = PerCoreTracker()
        ret = True
        for key, value in self.items():
            if key in other.keys():
                rv[key] = value == other[key]
                ret = rv[key] or ret
        return ret, rv

    def __int__(self, ndigits):
        for key, value in self.items():
            self[key] = int(value)
        return self

    def __round__(self, ndigits):
        for key, value in self.items():
            self[key] = round(value, ndigits)
        return self

    def scalar_mul(self, val):
        for key, value in self.items():
            self[key] = value * val
        return self


def signal_handler(_signal, _frame):
    """ Handle SIGINT"""
    print("\nExiting ...")
    exit(0)

def writemsr(msr, val, cpu=-1):
    """
    Function for writing to an msr register
    """
    try:
        if cpu == -1:
            for cpu_msr in glob.glob('/dev/cpu/[0-9]*/msr'):
                file_id = os.open(cpu_msr, os.O_WRONLY)
                os.lseek(file_id, msr, os.SEEK_SET)
                os.write(file_id, struct.pack('Q', val))
                os.close(file_id)
        else:
            file_id = os.open('/dev/cpu/%d/msr' % (cpu), os.O_WRONLY)
            os.lseek(file_id, msr, os.SEEK_SET)
            os.write(file_id, struct.pack('Q', val))
            os.close(file_id)
    except:
        raise OSError("msr module not loaded (run modprobe msr)")

def readmsr(msr, cpu=0):
    """
    function for readin an msr register
    """
    try:
        file_id = os.open('/dev/cpu/%d/msr' % cpu, os.O_RDONLY)
        os.lseek(file_id, msr, os.SEEK_SET)
        val = struct.unpack('Q', os.read(file_id, 8))
        os.close(file_id)
        return val[0]
    except:
        raise OSError("msr module not loaded (run modprobe msr)")

def get_percore_energy(cpulist=[0]):
    return [readmsr(AMD_MSR_CORE_ENERGY, i) & 0xFFFFFFFF for i in cpulist]

def update_delta(before, after):
    """ Takes two PerCoreTracker Dicts and returns update delta """
    if (before is None) or (after is None):
        return 0
    lesser = (after < before)
    if  lesser[0]:
        # One of the values has over-flowed
        ret = PerCoreTracker()

        for key, value in lesser[1].items():
            if value:
                ret[key] = 0x100000000 + after[key]
            else:
                ret[key] = after[key] - before[key]

        return ret
    else:
        # no overflow return difference
        return after - before

def get_units():
    result = readmsr(AMD_MSR_PWR_UNIT, 0)
    power_unit = 0.5 ** (result & 0xF)
    energy_unit = 0.5 **  ((result >> 8) & 0x1F)
    time_unit = 0.5 ** ((result >> 16) & 0xF)

    print(hex(result), " ", power_unit, " ", energy_unit, " ", time_unit)

    return energy_unit

def main():
    if os.geteuid() != 0:
        raise OSError("Need sudo to run")
    else:
        # ensure modprobe msr is run
        subprocess.run(["modprobe", "msr"])

    tree = cpu_tree()
    cpus = [list(tree[0][i].keys())[0] for i in range(psutil.cpu_count(logical=False))]
    for i in cpus:
        print(format(readmsr(AMD_MSR_CORE_ENERGY, i), '08X'))
    zeros = [0 for i in cpus]

    track_energy = PerCoreTracker(dict(zip(cpus,zeros)))
    energy_unit = get_units()
    while(True):
        before = PerCoreTracker(dict(zip(cpus, get_percore_energy(cpus))))
        sleep(1)
        after = PerCoreTracker(dict(zip(cpus, get_percore_energy(cpus))))
        delta = update_delta(before, after)
        track_energy = track_energy + delta.scalar_mul(energy_unit)
        print(round(track_energy,2), "\n", round(delta,2), "\n________")

## Starting point
if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    main()
