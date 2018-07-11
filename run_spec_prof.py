
import psutil
from msr import setup_perf
from frequency import *
from launcher import *

## Setup perf registers and set frequency to max
setup_perf()
max_freq = set_to_max_freq()

## Read in the workloads and run
for work in parse_file("input"):
    print(work[1][0], str(max_freq))
    f = open("/firestorm/output/spec2017/"+work[1][0].strip("./")+"_"+str(max_freq), "w+")
    f.flush()
    tstat = psutil.Popen(args=["/home/guliani/kernels/tools/turbostat/turbostat", "--debug", "--interval=1", "--add=msr0xC00000E9,u64,cpu,sec,raw,RetI"], stdout=f)
    run_on_core(work, cpu=0)
    f.close()
    tstat.kill()
