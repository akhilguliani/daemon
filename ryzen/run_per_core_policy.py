
import sys
import psutil
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
pwr_step = 5
bounds = get_freq_bounds()

cur_lim = set_rapl_limit(85)
input_file = sys.argv[1]

list_limits = [85,55,50,45,40]

for cur_lim in list_limits[:]:
    # reset to max frequency
    cur_freq = set_to_freq(bounds[1])
    # Update Limit
    cur_lim = set_rapl_limit(cur_lim)
    ## Read in the workloads and run
    work = parse_file(input_file)
    print('./'+input_file, str(cur_freq), str(cur_lim))
    f = open("/mydata/output/fairness/"+input_file+"_"+str(cur_freq)+"_"+str(cur_lim), "w+")
    f.flush()
    tstat = psutil.Popen(args=["turbostat", "--debug", "--interval=1"], stdout=f)
    run_on_cores_restart(work, copies=10, rstrt_even=False)
    tstat.kill()
    f.close()
