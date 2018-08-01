
import sys
from time import time
import psutil
from msr import setup_perf
from frequency import *
from launcher import *

## Setup perf registers and set frequency to max
# setup_perf()
# ensure MSR module is loaded
psutil.Popen(args=["modprobe","msr"])
# set govornor to userspace and freq to max possible
set_gov_userspace()
setup_rapl()
cur_freq = set_to_max_freq()
cur_lim = set_rapl_limit(85)

# get freq bounds and iterate from max to min freq in step-size
freq_step_size = 100000
bounds = get_freq_bounds()

input_file = sys.argv[1]

file_name = input_file+str(time())

print(file_name)

set_seq_freqs(2200000, freq_step_size, 10)

## Read in the workloads and run
r = parse_file(input_file)
f = open("/mydata/output/test/"+file_name, "w+")
f.flush()
tstat = psutil.Popen(args=["turbostat", "--debug", "--interval=1"], stdout=f)
run_multiple_on_cores(r)
tstat.kill()
f.close()
