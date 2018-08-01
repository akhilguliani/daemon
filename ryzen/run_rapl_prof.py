
import sys
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

# get freq bounds and iterate from max to min freq in step-size
freq_step_size = 100000
pwr_step = 10
bounds = get_freq_bounds()
cur_lim = 50

cur_lim = set_rapl_limit(cur_lim)
input_file = sys.argv[1]

while cur_lim > 46:
    # reset to max frequency
    cur_freq = set_to_max_freq()
    while cur_freq >= bounds[0]:
        ## Read in the workloads and run
        for work in parse_file(input_file):
            print(work[1][0], str(cur_freq), str(cur_lim))
            f = open("/mydata/output/rapl/"+work[1][0].strip("./")+"_"+str(cur_freq)+"_"+str(cur_lim), "w+")
            f.flush()
            tstat = psutil.Popen(args=["turbostat", "--debug", "--interval=1"], stdout=f)
            run_on_all_cores(work, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
            tstat.kill()
            f.close()
        cur_freq = set_to_freq_odd(cur_freq - freq_step_size)
    cur_lim = set_rapl_limit(cur_lim - pwr_step)
