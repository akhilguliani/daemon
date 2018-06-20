
import os
import signal
import subprocess
from time import sleep
import psutil
from topology import cpu_tree
from msr import AMD_MSR_CORE_ENERGY, writemsr, readmsr, get_percore_msr, get_percore_energy, get_units
from tracker import PerCoreTracker, update_delta, update_delta_32
from frequency import *

def signal_handler(_signal, _frame):
    """ Handle SIGINT"""
    print("\nExiting ...")
    exit(0)

def check_for_sudo_and_msr():
    if os.geteuid() != 0:
        raise OSError("Need sudo to run")
    else:
        # ensure modprobe msr is run
        subprocess.run(["modprobe", "msr"])

def setup_perf():
    val = readmsr(0xC0010015,0)
    for i in range(16):
        writemsr(0xC0010015, 0x4B200011, i)

def main():
    # get cpu topology
    tree = cpu_tree()

    perf_msr = 0xC00000E9
    setup_perf()
    # get cpu id's as a list
    cpus = [list(tree[0][i].keys())[0] for i in range(psutil.cpu_count(logical=False))]

    track_energy = PerCoreTracker(dict(zip(cpus, [0 for i in cpus])))
    track_perf =  PerCoreTracker(dict(zip(cpus, [0 for i in cpus])))

    power_tracker = PerCoreTracker(dict(zip(cpus, [0 for i in cpus])))

    energy_unit = get_units()

    set_gov_userspace()

    for i in cpus:
        print(get_freq_bounds())

    first = True
    old_freq = [None] * len(cpus)

    while(True):
        before = PerCoreTracker(dict(zip(cpus, get_percore_energy(cpus))))
        perf_before = PerCoreTracker(dict(zip(cpus, get_percore_msr(perf_msr, cpus))))
        sleep(1)
        after = PerCoreTracker(dict(zip(cpus, get_percore_energy(cpus))))
        delta = update_delta_32(before, after)
        perf_after = PerCoreTracker(dict(zip(cpus, get_percore_msr(perf_msr, cpus))))
        track_energy = track_energy + delta.scalar_mul(energy_unit)
        perf_delta = update_delta(perf_before, perf_after)
        track_perf = track_perf + perf_delta
        #print(round(track_energy,3), "\n", round(delta,3), "\n*_______")
        print(round(delta,3), "\n*_______")
        #print(round(track_perf,3), "\n", round(perf_delta,3), "\n________")
        print(round(perf_after,3), "\n________")

        curr_power = delta.scalar_mul(1000)

        for i in range(3):
            old_freq[i] = keep_limit(curr_power[cpus[i]], 5000, cpus[i], old_freq[i], first)

        first = False


## Starting point
if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    check_for_sudo_and_msr()
    main()
