
import os
import signal
import subprocess
from time import sleep
import psutil
import matplotlib.pyplot as plt
from topology import cpu_tree
from msr import AMD_MSR_CORE_ENERGY, writemsr, readmsr, get_percore_msr, get_percore_energy, get_units, setup_perf
from tracker import PerCoreTracker, update_delta, update_delta_32
from frequency import *
from launcher import *
from operator import itemgetter

def signal_handler(_signal, _frame):
    """ Handle SIGINT"""
    print("\nExiting ...")
    plt.show()
    exit(0)

def check_for_sudo_and_msr():
    """ Check if we are root and have the msr driver loaded in"""
    if os.geteuid() != 0:
        raise OSError("Need sudo to run")
    else:
        # ensure modprobe msr is run
        subprocess.run(["modprobe", "msr"])

def launch_all(list_proc):
    """Launch all the process in the list on successive cores"""
    i = 0
    retval = []
    retdict = {}
    for proc in list_proc:
        _p = launch_on_core(proc, cpu=i*2)
        retval.append(_p)
        retdict.update({i*2:_p.as_dict()})
        i = i+1
    return retdict

def plot_all(freq_dict, pwr_dict, perf_dict, tick, cpus, pwr_limits):
    grid_size = len(cpus)
    c = ['m','b','g','k','m','b','g','k']
    ax = []
    for i in range(len(cpus)):
        if i == 0:
            ax.append(plt.subplot(3, grid_size, i+1))
        else:
            plt.subplot(3, grid_size, i+1, sharey=ax[0])
        plt.scatter(tick, freq_dict[cpus[i]], marker='.', color=c[i])
        plt.ylim(ymin=1000000, ymax=3600000)

        if i == 0:
            ax.append(plt.subplot(3, grid_size, i+1+len(cpus)))
        else:
            plt.subplot(3, grid_size, i+len(cpus)+1, sharey=ax[1])
        plt.axhline(y=pwr_limits[i], color='r', linestyle='-')
        plt.scatter(tick, pwr_dict[cpus[i]], marker='.', color=c[i])
        plt.ylim(ymin=0, ymax=12000)

        if i == 0:
            ax.append(plt.subplot(3, grid_size, i+(2*len(cpus))+1))
        else:
            plt.subplot(3, grid_size, i+(2*len(cpus))+1, sharey=ax[2])
        plt.scatter(tick, perf_dict[cpus[i]], marker='.', color=c[i])
        #plt.ylim(ymin=0)
    plt.draw()
    plt.pause(0.1)


def main():
    """ Main function """
    # get cpu topology
    tree = cpu_tree()

    perf_msr = 0xC00000E9
    setup_perf()
    energy_unit = get_units()
    set_gov_userspace()
    set_to_max_freq()

    # get cpu id's as a list
    cpus = [list(tree[0][i].keys())[0] for i in range(psutil.cpu_count(logical=False))]

    track_energy = PerCoreTracker(dict(zip(cpus, [0 for i in cpus])))
    track_perf = PerCoreTracker(dict(zip(cpus, [0 for i in cpus])))
    power_tracker = PerCoreTracker(dict(zip(cpus, [0 for i in cpus])))
    first = True
    old_freq = [None] * len(cpus)
    count = 0
    list_procs = parse_file("input3")
    limit = 24
    max_per_core = 10
    list_procs.sort(key=itemgetter(3))
    high = [r for r in list_procs if r[3] < 0]
    total_shares = sum([r[2] for r in high])
    shares_per_app = [r[2]/total_shares for r in high]
    print(total_shares, shares_per_app)
    limits = [r*limit*1000 if r*limit < max_per_core else max_per_core*1000 for r in shares_per_app]
# Adjust limits so that excess power can overflow to the rest
#    shares_per_watt = [x[2]/y for x,y in zip(high, limits)]
    change = PerCoreTracker()
#    limits = [5000, 8000, 6000, 10000]
    launch_all(high)

    while True:
        before = PerCoreTracker(dict(zip(cpus, get_percore_energy(cpus))))
        perf_before = PerCoreTracker(dict(zip(cpus, get_percore_msr(perf_msr, cpus))))
        sleep(1)
        after = PerCoreTracker(dict(zip(cpus, get_percore_energy(cpus))))
        delta = update_delta_32(before, after)
        perf_after = PerCoreTracker(dict(zip(cpus, get_percore_msr(perf_msr, cpus))))
        track_energy = track_energy + delta.scalar_mul(energy_unit)
        perf_delta = update_delta(perf_before, perf_after)
        track_perf = track_perf + perf_delta

        delta.scalar_mul(1000)

        ## Percent change
        if first:
            power_tracker = delta
        else:
            change = (abs(delta - power_tracker) / power_tracker).scalar_mul(100)
            power_tracker = (power_tracker).scalar_mul(0.7) + (delta).scalar_mul(0.3)

        for i in range(4):
            #if change == {} or (change[cpus[i]] < 1 and delta[cpus[i]] < limits[i]):
            #    continue
            #if i == 0:
            #    continue
            old_freq[i] = keep_limit(power_tracker[cpus[i]], limits[i], cpus[i], old_freq[i], first)

        print(round(power_tracker, 3))
        # print(round(change, 3), "\n")
        # print(old_freq)
        f_dict = dict(zip(cpus, [read_freq_real(cpu=i) for i in cpus]))
        print(f_dict)
        print(round(perf_after, 3), "\n________")

        first = False
        count = count + 1
        plot_all(f_dict, power_tracker, track_perf, count, cpus[:len(high)], limits)

## Starting point
if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    check_for_sudo_and_msr()
    main()
