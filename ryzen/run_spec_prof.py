
import sys
import psutil
from msr import setup_perf
from frequency import *
from launcher import *

## Setup perf registers and set frequency to max
perf_dir = "/mydata/linux-4.17.8/tools/perf"
perf_args = shlex.split("./perf stat -I 1000 -e instructions -A -x ,")
# ensure MSR module is loaded
psutil.Popen(args=["modprobe","msr"])
# set govornor to userspace and freq to max possible
set_gov_userspace()
cur_freq = set_to_max_freq()

# get freq bounds and iterate from max to min freq in step-size
step_size=100000
cur_freq = set_to_freq(cur_freq - step_size)
bounds = get_freq_bounds()
while(cur_freq >= bounds[0]):
list_freqs = [i*step_size for i in range(21,8,-1)]
#for cur_freq in [22*step_size]:
    ## Read in the workloads and run
    # cur_freq = set_to_freq(cur_freq)
    for work in parse_file(sys.argv[1]):
        print(work[1][0], str(cur_freq))
        f = open("/mydata/output/rapl_perf/"+work[1][0].strip("./")+"_"+str(cur_freq), "w+")
        pf = open("/mydata/output/rapl_perf/perf_"+work[1][0].strip("./")+"_"+str(cur_freq), "w+")
        f.flush()
        pf.flush()
        tstat = psutil.Popen(args=["turbostat", "--debug", "--interval=1"], stdout=f)
        perf = subprocess.Popen(perf_args, stderr=pf, cwd=perf_dir)
        run_on_all_cores(work, [0])
        f.close()
        pf.close()
        perf.kill()	
        tstat.kill()
    cur_freq = set_to_freq(cur_freq-step_size)
