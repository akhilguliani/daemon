
import sys
from time import time
import psutil
from msr import setup_perf
from frequency import *
from launcher import *

## Setup perf registers and set frequency to max
setup_perf()
# ensure MSR module is loaded
psutil.Popen(args=["modprobe","msr"])
# set govornor to userspace and freq to max possible
set_gov_userspace()
cur_freq = set_to_max_freq()

input_file = sys.argv[1]

max_cores= 8
core_list = [i*2 for i in range(max_cores)]

set_seq_freqs([3400000, 3000000, 2200000], max_cores)

## Read in the workloads and run
r = parse_file(input_file)
tfile_name = input_file+str(time())
f = open("/mydata/output/percore/"+tfile_name, "w+")
f.flush()
tstat = psutil.Popen(args=["/home/guliani/kernels/tools/turbostat/turbostat", "--debug", "--interval=1", "--add=msr0xC00000E9,u64,cpu,sec,raw,RetI"], stdout=f)
print(tfile_name)
run_multiple_on_cores(r, cores=core_list)
tstat.kill()
f.close()
