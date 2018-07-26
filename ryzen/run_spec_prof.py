
import sys
import psutil
from msr import setup_perf
from frequency import *
from launcher import *

## Setup perf registers and set frequency to max
psutil.Popen(args=["modprobe","msr"])
setup_perf()
set_gov_userspace()
cur_freq = set_to_max_freq()
bounds = get_freq_bounds_ryzen()

# Skipping The first P-State as we have the values for that
step_size=100000
cur_freq = set_to_freq(cur_freq-step_size)

while(cur_freq >= bounds[0]):
    ## Read in the workloads and run
    for work in parse_file(sys.argv[1]):
        print(work[1][0], str(cur_freq))
        f = open("/firestorm/output/spec2017/"+work[1][0].strip("./")+"_"+str(cur_freq), "w+")
        f.flush()
        tstat = psutil.Popen(args=["/home/guliani/kernels/tools/turbostat/turbostat", "--debug", "--interval=1", "--add=msr0xC00000E9,u64,cpu,sec,raw,RetI"], stdout=f)
        run_on_core(work, cpu=0)
        f.close()
        tstat.kill()
    cur_freq = set_to_freq(cur_freq-step_size)

