
"""
CPU time and temperatures to disambiguate energy values
"""

import time
import signal
import sys
import psutil

def signal_handler(_signal, _frame):
    """ SIGINT Handler for gracefull exit """
    print("\nExiting ...")
    sys.exit(0)

def diff_pcputimes(_t1, _t2):
    """ Diff function for per cpu times class """
    print(type(_t1))
    assert _t1._fields == _t2._fields, (_t1, _t2)
    field_deltas = []
    for field in psutil._common.pcputimes._fields:
        field_delta = getattr(_t2, field) - getattr(_t1, field)
        field_delta = max(0, field_delta)
        field_deltas.append(field_delta)
    return psutil._common.pcputimes(*field_deltas)

def get_all_busy_time():
    """ Get per-CPU busy times """
    times = psutil.cpu_times(percpu=True)
    busy_times = []
    for cpu in range(psutil.cpu_count()):
        busy_times.append(psutil._cpu_busy_time(times[cpu]))
    return busy_times

def main():
    """ Main Function """

    ttrack = {}
    temps = (psutil.sensors_temperatures())['coretemp']
    for temp in temps:
        ttrack[getattr(temp, 'label')] = getattr(temp, 'current')
        print(temp)

    while True:
        prev = get_all_busy_time()
        prev_stats = {}
        for _proc in psutil.process_iter():
            _stat = _proc.as_dict(attrs=['pid', 'name', 'cpu_num', 'cpu_times'])
            new_stats = {}
            if "FIRESTARTER" in  _stat['name']:
                prev_stats[_stat['pid']] = _stat.copy()


        time.sleep(1)
        print("\n************\n")
        # print(psutil.cpu_percent(percpu=True))
        # print(psutil.sensors_temperatures())
        temps = (psutil.sensors_temperatures())['coretemp']
        for temp in temps:
            ttrack[getattr(temp, 'label')] += getattr(temp, 'current')
            ttrack[getattr(temp, 'label')] = round(ttrack[getattr(temp, 'label')]/2, 1)
            #print(temp)
        print(ttrack)

        mintemp = min(ttrack.values())
        maxtemp = max(ttrack.values())
        intensity = {}
        for key, value in ttrack.items():
            intensity[key] = round((value - mintemp) / (maxtemp - mintemp), 2)
        print(intensity)
        print("______")

        curr_bzy = get_all_busy_time()
        dtime = [max(round(i-j, 2), 0) for i, j in zip(curr_bzy, prev)]
        print(dtime)
        new_stats = {}
        for _proc in psutil.process_iter():
            _stat = _proc.as_dict(attrs=['pid', 'name', 'cpu_num', 'cpu_times'])
            if "FIRESTARTER" in  _stat['name']:
                new_stats[_stat['pid']] = _stat.copy()

        print(new_stats)

        for key, value in new_stats.items():
            if key in prev_stats.keys():
                dtimes = diff_pcputimes(prev_stats[key]['cpu_times'], value['cpu_times'])
                print(key, " : ", sum(dtimes))

##########################
#### Starting loop
##########################

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    main()
