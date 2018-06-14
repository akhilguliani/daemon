
import psutil
import subprocess
import time

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

def power_at_freq(in_freq):
    # freq is represented as 8 = 800MHz; 42 = 4200MHz
    bounds = get_freq_bounds()
    if in_freq <= bounds[1] and in_freq >= bounds[0]:
        freq = in_freq/100000
    elif in_freq < bounds[0]:
        freq = 8
    elif in_freq > bounds[1]:
        freq = 42
    return (0.0211*(freq**2) - 0.4697*freq + 7.7535)*1000

def freq_at_power(power):
    return int(-0.0773*((power/1000)**2)+ 3.7436*(power/1000) - 4.6404)*100000
    
def change_freq(target_power, increase=False):
    """ Update frequency based on target power and power model """
    # power differential to freq reduction factor
    new_freq = freq_at_power(target_power)
    old_freq = int(read_freq())
    # print(new_freq, old_freq, target_power)

    if abs(old_freq - new_freq) <= 1000:
        return

    new_power = power_at_freq(new_freq)

    if increase:
        while new_power < target_power:
            old_power = power_at_freq(new_freq)
            new_freq = new_freq + 100000
            new_power = power_at_freq(new_freq)
            if new_power == old_power:
                new_freq = new_freq - 100000
                break
            # print(new_freq, old_freq, new_power, target_power)
    else:
        while new_power > target_power:
            old_power = power_at_freq(new_freq)
            new_freq = new_freq - 100000
            new_power = power_at_freq(new_freq)
            # print(new_freq, old_freq, new_power)
            if new_power == old_power:
                new_freq = new_freq + 100000
                break

    # WARN: Hardecoded cpu numbers below
    for i in range(psutil.cpu_count()):
        write_freq(new_freq, i)

    return

def change_freq_std(target_pwr, current_pwr, increase=False):
    """ Update frequency based on target power and actulal power value """
    # power differential to freq reduction factor
    new_freq = int(read_freq())

    power_diff = abs(current_pwr - target_pwr)
    step = 100000

    # Select the right step size
    if power_diff < 900:
        # to close better settle than oscillate
        return
    elif power_diff > 3000 and power_diff < 10000:
        step = 200000
    elif power_diff > 10000:
        step = 500000

    if increase:
        new_freq = new_freq + step
    else:
        new_freq = new_freq - step

    # WARN: Hardecoded cpu numbers below
    for i in range(psutil.cpu_count()):
        write_freq(new_freq, i)

    return

def keep_limit(curr_power, limit=20000, first_limit=True):
    """ Follow the power limit """
    new_limit = limit

    if not first_limit:
        if curr_power - limit > 0 and new_limit > 5000:
            new_limit = new_limit - abs(curr_power - new_limit)/2
            #new_limit = new_limit - 1000
        elif curr_power - limit < 0 and new_limit > 5000:
            new_limit = new_limit + abs(curr_power - new_limit)/4
#            #new_limit = new_limit + 1000

    # print("In keep_limit ", limit)
        if curr_power > limit:
            # reduce frequency
            change_freq_std(new_limit, curr_power)
        elif curr_power < limit:
            # print("Increase")
            change_freq_std(new_limit, curr_power, increase=True)
    else:
        # First Step
        if curr_power > limit:
            # reduce frequency
            change_freq(new_limit)
        elif curr_power < limit:
            # print("Increase")
            change_freq(new_limit, increase=True)
    return

