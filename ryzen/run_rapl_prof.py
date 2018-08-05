
import sys
import psutil
import shlex
from frequency import set_gov_userspace, set_to_max_freq, set_to_freq_odd, setup_rapl, get_freq_bounds, set_rapl_limit
from launcher import parse_file, run_on_multiple_cores_timeout

def setup_perf_file(file_handle):
    perf_dir = "/mydata/linux-4.17.8/tools/perf"
    perf_args = shlex.split("./perf stat -I 1000 -e instructions -A -x ,")
    return psutil.Popen(perf_args, stderr=file_handle, cwd=perf_dir)

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
cur_lim = 85

cur_lim = set_rapl_limit(cur_lim)
input_file = sys.argv[1]

for cur_lim in [55, 50, 45, 40]:
    # reset to max frequency
    set_rapl_limit(cur_lim)
    cur_freq = set_to_max_freq()
    cur_freq = set_to_freq_odd(cur_freq - 24*freq_step_size)
    while cur_freq >= bounds[0]:
        ## Read in the workloads and run
        cur_freq = set_to_freq_odd(cur_freq - freq_step_size)
        work = parse_file(input_file)
        print(work)
        print(work[0][1][0], str(cur_freq), str(cur_lim))
        pfile = open("/mydata/output/raplPerf/"+work[0][1][0].strip("./")+"_"+str(cur_freq)+"_"+str(cur_lim), "w+")
        pfile.flush()
        f = open("/mydata/output/rapl/inputs/"+work[0][1][0].strip("./")+"_"+str(cur_freq)+"_"+str(cur_lim), "w+")
        f.flush()
        tstat = psutil.Popen(args=["turbostat", "--debug", "--interval=1"], stdout=f)
        perf = setup_perf_file(pfile)
        # run_on_all_cores(work, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
        # run_on_cores_restart2(work, copies=10, rstrt_even=True)
        procs = run_on_multiple_cores_timeout(work, cores=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], timeout=500)
        perf.kill()
        pfile.close()
        tstat.kill()
        f.close()
        for p in procs:
            p.terminate()
        kill_procs = psutil.Popen(args=["killall", work[0][1][0].strip("./")])
        psutil.wait_procs([kill_procs])
        #cur_freq = set_to_freq_odd(cur_freq - freq_step_size)


set_to_max_freq()
set_rapl_limit(85)