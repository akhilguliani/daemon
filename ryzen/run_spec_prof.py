
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
cur_freq = set_to_max_freq()

# get freq bounds and iterate from max to min freq in step-size
step_size=100000
bounds = get_freq_bounds()
while(cur_freq >= bounds[0]):
    ## Read in the workloads and run
    for work in parse_file(sys.argv[1]):
        print(work[1][0], str(cur_freq))
        f = open("/mydata/output/spec2017/"+work[1][0].strip("./")+"_"+str(cur_freq), "w+")
        f.flush()
        tstat = psutil.Popen(args=["turbostat", "--debug", "--interval=1"], stdout=f)
        run_on_core(work, cpu=0)
        f.close()
        tstat.kill()
    cur_freq = set_to_freq(cur_freq-step_size)
