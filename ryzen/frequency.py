
import psutil
import subprocess
import time
import math
from msr import update_pstate_freq

TDP = 85000

def get_freq_bounds(cpu=0):
    bounds = [0, 0]
    freq_file = open("/sys/devices/system/cpu/cpu%d/cpufreq/scaling_max_freq" % cpu, 'r')
    bounds[1] = int(freq_file.read())
    freq_file.close()
    freq_file = open("/sys/devices/system/cpu/cpu%d/cpufreq/scaling_min_freq" % cpu, 'r')
    bounds[0] = int(freq_file.read())
    freq_file.close()
    return bounds

def get_freq_bounds_ryzen(cpu=0):
    bounds = [800000, 3400000]
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

def quantize(value):
    ret = int(round(value / 100000, 0))
    return ret*100000

def read_freq(cpu=0):
    f_file = "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_cur_freq" % cpu
    freq_file = open(f_file)
    ret_val = freq_file.read()
    freq_file.close()
    return str(quantize(int(ret_val)))

def read_freq_real(cpu=0):
    """ Return Real frequency as reported to cpufreq"""
    f_file = "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_cur_freq" % cpu
    freq_file = open(f_file)
    ret_val = freq_file.read()
    freq_file.close()
    return int(ret_val)

def write_freq(val, cpu=0):
    bounds = get_freq_bounds()
    if val <= bounds[1] and val >= bounds[0]:
#        print("Changing Freq to ", str(val))
        f_file = "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_setspeed" % cpu
        freq_file = open(f_file, 'w')
        freq_file.write(str(val))
        freq_file.close()
    return

def update_write_freq(val, cpu=0):
    """ AMD Ryzen Specific write frequency loop
        Here we update the relevant P-State to match the val given
        the h/w can override us
    """
    states = [2200000, 3000000, 3400000]
    if val in states:
        write_freq(val, cpu)
    elif val > states[0] and val < states[-1]:
        # Update state 1 to mean val
        update_pstate_freq(val, 1)
        write_freq(states[1], cpu)
    elif val < states[0] and val >= 800000:
        update_pstate_freq(val, 2)
        write_freq(states[0], cpu)
    return

def set_to_max_freq(cpu=None):
    """ Set all the cpus to max frequency"""
    max_freq = get_freq_bounds()[1]
    if cpu is None:
        for c in range(psutil.cpu_count()):
            write_freq(max_freq, c)
    else:
        write_freq(max_freq, cpu)
    return max_freq

def set_to_freq(freq, cpu=None):
    """ Set all the cpus to a given frequency"""
    if cpu is None:
        for c in range(psutil.cpu_count()):
            write_freq(freq, c)
    else:
        write_freq(freq, cpu)
    return freq

def set_to_freq_odd(freq):
    """ Set all the cpus to a given frequency"""
    for c in range(psutil.cpu_count()):
        if not c % 2 == 0:
            write_freq(freq, c)
    return freq

def set_seq_freqs(start_freq, step, num_cores):
    """ Set all the cpus to sequentially reducing frequencies for Xeon"""
    curr_freq = start_freq
    for c in range(num_cores):
        write_freq(curr_freq, c)
        write_freq(curr_freq, c+21)
        curr_freq = curr_freq - step
    return


def power_at_freq(in_freq):
    # freq is represented as 8 = 800MHz; 42 = 4200MHz
    bounds = get_freq_bounds_ryzen()
    if in_freq <= bounds[1] and in_freq >= bounds[0]:
        freq = in_freq/100000
    elif in_freq < bounds[0]:
        freq = 8
    elif in_freq > bounds[1]:
        freq = 34
    return (0.0211*(freq**2) - 0.4697*freq + 7.7535)*1000

def freq_at_power(power):
    return int(-0.0773*((power/1000)**2)+ 3.7436*(power/1000) - 4.6404)*100000

def change_freq(target_power, cpu=0, increase=False):
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
    else:
        while new_power > target_power:
            old_power = power_at_freq(new_freq)
            new_freq = new_freq - 100000
            new_power = power_at_freq(new_freq)
            # print(new_freq, old_freq, new_power)
            if new_power == old_power:
                new_freq = new_freq + 100000
                break

    print("change_freq:", new_freq, old_freq, new_power, target_power)
    # WARN: Hardecoded cpu numbers below
    #for i in range(psutil.cpu_count()):
    update_write_freq(new_freq, cpu)
    update_write_freq(new_freq, cpu+1)

    return

def change_freq_std(target_pwr, current_pwr, old_freq=None, cpu=0, increase=False):
    """ Update frequency based on target power and actulal power value """
    # TODO: Fix this function - try to determine when to stop
    # probably better to make this a class and track some of the variables and
    # have a way of resetting

    # power differential to freq reduction factor
    new_freq = None
    if old_freq is None:
        new_freq = int(read_freq(cpu))
    else:
        new_freq = old_freq


    power_diff = abs(current_pwr - target_pwr)
    step = 100000

    # Select the right step size
    if power_diff < 500:
        # to close better settle than oscillate
        return None
    elif power_diff > 3000 and power_diff < 10000:
        step = 100000
    elif power_diff > 10000:
        step = 500000

    if increase:
        new_freq = new_freq + step
    else:
        new_freq = new_freq - step

    bounds = get_freq_bounds()

    if new_freq < bounds[0]:
        new_freq = bounds[0]
    if new_freq > bounds[1]:
        new_freq = bounds[1]

    print("ch_freq_std ", cpu, target_pwr, new_freq, increase, power_diff)
    # WARN: Hardecoded cpu numbers below
    write_freq(new_freq, cpu)
    if (cpu % 2) == 0:
        update_write_freq(new_freq, cpu+1)
    else:
        update_write_freq(new_freq, cpu-1)

    return new_freq

def keep_limit(curr_power, limit=10000, cpu=0, last_freq=None, first_limit=True):
    """ Follow the power limit """
    new_limit = limit
    old_freq = None

    if not first_limit:
        if curr_power - limit > 0 and new_limit > 1000:
            new_limit = new_limit - abs(curr_power - new_limit)/2
            #new_limit = new_limit - 1000
        elif curr_power - limit < 0 and new_limit > 1000:
            new_limit = new_limit + abs(curr_power - new_limit)/4
#            #new_limit = new_limit + 1000

    # print("In keep_limit ", limit)
        if curr_power > limit:
            # reduce frequency
            old_freq = change_freq_std(new_limit, curr_power, last_freq, cpu)
        elif curr_power < limit:
            # print("Increase")
            old_freq = change_freq_std(new_limit, curr_power, last_freq, cpu, increase=True)
    else:
        # First Step
        if curr_power > limit:
            # reduce frequency
            change_freq(new_limit, cpu)
        elif curr_power < limit:
            # print("Increase")
            change_freq(new_limit, cpu, increase=True)
    return old_freq

def set_per_core_freq(freq_list, cores, start_at=0):
    """ Write Quantized Frequency Limits """
    for i in range(start_at, cores):
        write_freq(quantize(freq_list[i]), i)
    return

def keep_limit_prop_freq(curr_power, limit, hi_freqs, low_freqs, hi_shares, low_shares, first_limit=False, lp_active=False):
    ## Write a new controller that takes in shares and power -> affects frequency
    # for Mixed priorities this controller also takes in core priorities with shares
    ### Lower Priority gets throttled to minimum till:
    ############# RAPL Limit Starts to drop
    ############# Or We have reached the lowest frequency (here we can start using DC to go lower)
    #### At lowest freq we should check how much HP is throttled, if below a threshold, then starve LP
    ## With Shares when we have to throttle the HP cores we do bin packing (Freq Shares we do 22 rounds for 22 levels)
    ###### At each level if the shares of the cores lie within threshold, we reduce their freq by one step starting from current
    ###### We also reduce the shares by the threshold delta (this way all apps get throttled eventually, and proportionally)
    ######## We continue with this trend till the power drops below limit or we reach
    # old_freq[i] = keep_limit(power_tracker[cpus[i]], limits[i], cpus[i], old_freq[i], first)
    tolerance = 200
    bounds = get_freq_bounds()
    max_per_core = max(hi_freqs)
    alpha = abs(limit-curr_power)/TDP
 
    if abs(curr_power - limit) < tolerance:
        # at power limit nothing todo
        return False
    elif (limit - curr_power) > -1*tolerance:
        # Below limit
        # We have excess power
        extra_freq = alpha * max_per_core
        ## distribute excess power - frequency among 
        # First Check if high power apps are at max freq
        if not (hi_shares is None):
            add_hi = [s * extra_freq for s in hi_shares]
            extra_freq = extra_freq - sum(add_hi)
            hi_freqs = [ x+y for x,y in zip(add_hi, hi_freqs)]
        if not first_limit:
            if extra_freq > 100000 and lp_active:
                if not (low_shares is None):
                    add_lo = [s * extra_freq for s in low_shares]
                    extra_freq = extra_freq - sum(add_lo)
                    low_freqs = [ x+y for x,y in zip(add_lo, low_freqs)]
                return True
            return False
    elif (curr_power - limit) > tolerance:
        # Above limit
        # We have no excess power
        # remove extra frequency from low power first
        extra_freq = alpha * max_per_core
        if lp_active and not(low_shares is None):
            rem_lo = [s * extra_freq for s in low_shares]
            extra_freq = extra_freq - sum(rem_lo)
            low_freqs = [ y-x for x,y in zip(rem_lo, low_freqs)]

        # remove remaining frequency from hi power
        if not (hi_shares is None):
            rem_hi = [s * extra_freq for s in hi_shares]
            extra_freq = extra_freq - sum(rem_hi)
            hi_freqs = [ y-x for x,y in zip(add_hi, hi_freqs)]
        return False
    return False

def keep_limit_priority(curr_power, limit, high_cpus=[], low_cpus=[], first_limit=True, lp_active=False):
    """ Follow the power limit for Intel skylake priority only"""
    tolerance = 200
    step = 100000
    bounds = get_freq_bounds()

    if abs(curr_power - limit) < tolerance:
        # at power limit
        return False

    if first_limit:
        # Check if we are above limt
        if (curr_power - limit) < -1*tolerance:
            # Below limit
            # We have excess power for low priority
            # Set low prio cores to lowest freq
            for core in low_cpus:
                write_freq(800000, cpu=core)
                write_freq(800000, cpu=20+core)
            return True
        elif (curr_power - limit) > tolerance:
            # Above limit
            # We have no excess power
            # Reduce freq for high priority cores by one step
            first_core = 0 if high_cpus == [] else high_cpus[0]
            curr_freq = int(read_freq(cpu=first_core))
            for core in high_cpus:
                write_freq(curr_freq - step, cpu=core)
                write_freq(curr_freq - step, cpu=20+core)
            return False
    else:
        if (limit - curr_power) > -1*tolerance:
            # Below limit
            # We have excess power
            # First Check if high power apps are at max freq
            first_core = 0 if high_cpus == [] else high_cpus[0]
            curr_freq = int(read_freq(cpu=first_core))
            for core in high_cpus:
                if curr_freq < bounds[1]:
                    write_freq(curr_freq + step, cpu=core)
                    write_freq(curr_freq + step, cpu=20+core)
                    # we can increase power for low priority tasks
            print("Below limit updating", lp_active, curr_freq)
            if curr_freq >= 2100000 and lp_active:
                for core in low_cpus:
                    curr_freq = int(read_freq(cpu=core))
                    if curr_freq < bounds[1]:
                        write_freq(curr_freq + step, cpu=core)
                        write_freq(curr_freq + step, cpu=20+core)
                return True
            return False
        elif (curr_power - limit) > tolerance:
            # Above limit
            # We have no excess power
            if lp_active:
                for core in low_cpus:
                    curr_freq = int(read_freq(cpu=core))
                    if curr_freq < bounds[1]:
                        write_freq(curr_freq - step, cpu=core)
                        write_freq(curr_freq - step, cpu=20+core)
                return True
            # Reduce freq for high priority cores by one step
            first_core = 0 if high_cpus == [] else high_cpus[0]
            curr_freq = int(read_freq(cpu=first_core))
            for core in high_cpus:
                write_freq(curr_freq - step, cpu=core)
                write_freq(curr_freq - step, cpu=20+core)
            return False

def set_rapl_limit(limit):
    """ set rapl limit in watts """
    rapl_file = "/sys/class/powercap/intel-rapl:0/constraint_0_power_limit_uw"
    multiplier = 1000000
    rapl = open(rapl_file, 'w')
    rapl.write(str(limit * multiplier))
    rapl.close()
    return limit

def setup_rapl():
    """ Enable RAPL with TDP limit and 0.09 Sec time window """
    rapl_dir = "/sys/class/powercap/intel-rapl:0/"
    rapl_file = rapl_dir + "constraint_0_power_limit_uw"
    # Find Max Limit Possible and write it as limit
    max_limit = open(rapl_dir + "constraint_0_max_power_uw")
    rapl = open(rapl_file, 'w')
    rapl.write(max_limit.read())
    rapl.close()
    max_limit.close()
    # set RAPL window time
    rapl_time = open(rapl_dir + "constraint_0_time_window_us", 'w')
    rapl_time.write("99942")
    rapl_time.close()
    # Enable RAPL limit
    enable = open(rapl_dir + "enabled", 'w')
    enable.write("1")
    enable.close()
    return
