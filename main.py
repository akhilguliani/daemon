
import os
import signal
import subprocess
from time import sleep
import psutil
from topology import cpu_tree
from msr import AMD_MSR_CORE_ENERGY, readmsr, get_percore_energy, get_units
from tracker import PerCoreTracker, update_delta
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

def main():
    # get cpu topology
    tree = cpu_tree()

    # get cpu id's as a list
    cpus = [list(tree[0][i].keys())[0] for i in range(psutil.cpu_count(logical=False))]

    track_energy = PerCoreTracker(dict(zip(cpus, [0 for i in cpus])))

    energy_unit = get_units()

    set_gov_userspace()

    print(get_freq_bounds())

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
    check_for_sudo_and_msr()
    main()
