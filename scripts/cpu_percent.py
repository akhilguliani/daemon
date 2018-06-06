import psutil
import time

ttrack = {}
temps = (psutil.sensors_temperatures())['coretemp']
for temp in temps:
    ttrack[getattr(temp,'label')] = getattr(temp,'current')
    print(temp)

def diff_pcputimes(t1, t2):
    print(type(t1))
    assert t1._fields == t2._fields, (t1, t2)
    field_deltas = []
    for field in psutil._common.pcputimes._fields:
        field_delta = getattr(t2, field) - getattr(t1, field)
        field_delta = max(0, field_delta)
        field_deltas.append(field_delta)
    return psutil._common.pcputimes(*field_deltas)

def get_all_busy_time():
    times = psutil.cpu_times(percpu=True)
    busy_times = []
    for cpu in range(psutil.cpu_count()):
        busy_times.append(psutil._cpu_busy_time(times[cpu]))
    return busy_times

while True:
    prev = get_all_busy_time()
    prev_stats = {}
    for _proc in psutil.process_iter():
        _stat = _proc.as_dict(attrs=['pid','name' ,'cpu_num' ,'cpu_times'])
        new_stats = {}
        if "FIRESTARTER" in  _stat['name']:
            prev_stats[_stat['pid']] = _stat.copy()


    time.sleep(1)
    print("\n************\n")
    # print(psutil.cpu_percent(percpu=True))
    # print(psutil.sensors_temperatures())
    temps = (psutil.sensors_temperatures())['coretemp']
    for temp in temps:
        ttrack[getattr(temp,'label')] += getattr(temp,'current')
        ttrack[getattr(temp,'label')] = ttrack[getattr(temp,'label')]/2
        #print(temp)
    print(ttrack)

    mintemp = min(ttrack.values())
    maxtemp = max(ttrack.values())
    intensity = {}
    for key in ttrack.keys():
        intensity[key] = round((ttrack[key] - mintemp) / (maxtemp - mintemp),2)
    print(intensity)
    print("______")

    a = get_all_busy_time()
    dtime = [ max(round(i-j, 2) , 0) for i,j in zip(a,prev) ]
    print(dtime)
    new_stats = {}
    for _proc in psutil.process_iter():
        _stat = _proc.as_dict(attrs=['pid','name' ,'cpu_num' ,'cpu_times'])
        if "FIRESTARTER" in  _stat['name']:
            new_stats[_stat['pid']] = _stat.copy()

    print(new_stats)

    for key in new_stats.keys():
        if key in prev_stats.keys():
           dtimes = diff_pcputimes(prev_stats[key]['cpu_times'], new_stats[key]['cpu_times'])
           print(key, " : ", sum(dtimes))
