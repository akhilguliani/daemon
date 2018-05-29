
from helper import *

def get_freq_bounds():
    bounds = [0, 0]
    freq_file = open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq", 'r')
    bounds[1] = int(freq_file.read())
    freq_file.close()
    freq_file = open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq", 'r')
    bounds[0] = int(freq_file.read())
    freq_file.close()
    return bounds

def set_gov_userspace():
    # Add check for intel_cpufreq
    driver_file = open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver")
    driver = driver_file.read()
    driver_file.close()

    if "cpufreq" in driver:
        for i in range(psutil.cpu_count()):
            gov_file = "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_governor" % i
            gfd = open(gov_file, 'w')
            gfd.write("userspace")
            gfd.close()
    else:
        print("Unspported Driver: please enable intel/acpi_cpufreq from kerenl cmdline")

def read_freq(cpu=0):
    f_file = "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_cur_freq" % cpu
    freq_file = open(f_file)
    ret_val = freq_file.read()
    freq_file.close()
    return ret_val

def write_freq(val, cpu=0):
    bounds = get_freq_bounds()
    if val <= bounds[1] and val >= bounds[0]:
#        print("Changing Freq to ", str(val))
        f_file = "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_setspeed" % cpu
        freq_file = open(f_file, 'w')
        freq_file.write(str(val))
        freq_file.close()
    return

## Functions for Skylake gold in cloudlab
def power_at_freq(in_freq):
    # freq is represented as 8 = 800MHz; 42 = 4200MHz
    bounds = get_freq_bounds()
    if in_freq <= bounds[1] and in_freq >= bounds[0]:
        freq = in_freq/100000
    elif in_freq < bounds[0]:
        freq = bounds[0]/100000
    elif in_freq > bounds[1]:
        freq = bounds[1]/100000
    # 0.012x2 - 0.1714x + 42.046
    return (0.012*(freq**2) - 0.1717*freq + 42.046)*1000

def freq_at_power(power):
    # -0.1661x2 + 17.797x - 440.35
    return int(-0.1661*((power/1000)**2)+ 17.797*(power/1000) - 440.35)*100000

## Functions for ADSL-SL01
"""
def power_at_freq(in_freq):
    # freq is represented as 8 = 800MHz; 42 = 4200MHz
    bounds = get_freq_bounds()
    if in_freq <= bounds[1] and in_freq >= bounds[0]:
        freq = in_freq/100000
    elif in_freq < bounds[0]:
        freq = bounds[0]/100000
    elif in_freq > bounds[1]:
        freq = bounds[1]/100000
    return (0.0211*(freq**2) - 0.4697*freq + 7.7535)*1000

def freq_at_power(power):
    return int(-0.0773*((power/1000)**2)+ 3.7436*(power/1000) - 4.6404)*100000
"""
