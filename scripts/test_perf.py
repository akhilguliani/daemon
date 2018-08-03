import subprocess
import shlex
import time
import matplotlib.pyplot as plt
import psutil

perf_dir = "/mydata/linux-4.17.8/tools/perf"

perf_args_txt = "./perf stat -I 1000 -e instructions -A -x ,"
perf_args = shlex.split(perf_args_txt)

perf = subprocess.Popen(perf_args, stderr=subprocess.PIPE, cwd=perf_dir, universal_newlines=True)
count = 0

while True:
    time.sleep(1)
    perf_arr = [perf.stderr.readline().strip().split(",")[2] for i in range(psutil.cpu_count())]
    print(perf_arr[:3])
#    for i in range(8):
#        plt.subplot(2, 4, i+1)
#        plt.scatter(count, perf_arr[i], color='C'+str(i))
#        plt.ylim(0, 1e10)
#    plt.draw()
#    plt.pause(0.5)
#    count += 1
#plt.show()
