
import sys
import psutil
import shlex
from multiprocessing import Process
from time import sleep
from frequency import set_gov_userspace, set_rapl_limit, set_to_max_freq, setup_rapl, set_to_freq, get_freq_bounds
from launcher import parse_file, run_on_multiple_cores_timeout, run_on_multiple_cores_forever

## Setup perf registers
perf_dir = "/mydata/linux-4.17.8/tools/perf"
perf_args = shlex.split("./perf stat -I 1000 -e instructions -A -x ,")

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
work = parse_file(input_file)

# run all applications
all_process = Process(target=run_on_multiple_cores_forever, args=(work, [0,1,2,3,4,5,6,7,8,9]))
all_process.start()
sleep(600)

for cur_lim in list_limits[:]:
    # reset to max frequency
    cur_freq = set_to_freq(bounds[1])
    # Update Limit
    cur_lim = set_rapl_limit(cur_lim)
    ## Read in the workloads and run

    print('./'+input_file, str(cur_freq), str(cur_lim))
    print(work[0][1][0].strip('./'), work[1][1][0].strip('./'))
    
    f = open("/mydata/output/fairness/"+input_file.split("/")[1]+"_"+str(cur_freq)+"_"+str(cur_lim), "w+")
    pf = open("/mydata/output/fairness/perf_"+input_file.split("/")[1]+"_"+str(cur_freq)+"_"+str(cur_lim), "w+")
    f.flush()
    pf.flush()
    tstat = psutil.Popen(args=["turbostat", "--debug", "--interval=1"], stdout=f)
    perf = psutil.Popen(perf_args, stderr=pf, cwd=perf_dir)
    
    sleep(600)

    tstat.kill()
    perf.kill()
    sleep(1)
    pf.close()
    f.close()

all_process.join(timeout=100)
all_process.terminate()

psutil.Popen(args=["killall", work[0][1][0].strip('./')])
psutil.Popen(args=["killall", work[1][1][0].strip('./')])
psutil.Popen(args=["killall", "python"])