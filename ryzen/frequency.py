
import psutil
import subprocess
import time
import math
from collections import Counter
from msr import update_pstate_freq, print_pstate_values, get_pstate_freqs

TDP = 95000

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
    from decimal import Decimal
    ret = int(Decimal(value/25000).quantize(Decimal("1"))*25000)
    if ret > 3400000:
        return 3400000
    if ret < 800000:
        return 800000
    return ret

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
    bounds = get_freq_bounds_ryzen()
    if val <= bounds[1] and val >= bounds[0]:
#        print("Changing Freq to ", str(val))
        f_file = "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_setspeed" % cpu
        freq_file = open(f_file, 'w')
        freq_file.write(str(val))
        freq_file.close()
    return

def ryzen_write_freq(val, bounds, cpu=0):
    """ AMD Ryzen Specific write frequency function
    This function is needed when we have more than two frequencies for the same P-state
    """
    states = [2200000, 3000000, 3400000]
    if val > bounds[0] and val <= bounds[1]:
        write_freq(states[1], cpu)
    elif val <= bounds[0] and val >= 400000:
        write_freq(states[0], cpu)
    elif val > bounds[1] and val <= bounds[2]:
        write_freq(states[2], cpu)
    return

def reset_pstates():
    states = [3400000, 3000000, 2200000]
    for i,val in enumerate(states):
        update_pstate_freq(val, i)
    return

def update_write_freq(val, cpu=0, turbo=False, update=True):
    """ AMD Ryzen Specific write frequency loop
        Here we update the relevant P-State to match the val given
        the h/w can override us
    """
    max_freq = 3400000
    if turbo:
        max_freq = 3800000
    states = [2200000, 3000000, 3400000]
    #if val in states:
    #    write_freq(val, cpu)
    if val > states[0] and val < states[1]:
        # Update state 1 to mean val
        if update:
            update_pstate_freq(val, 1)
        write_freq(states[1], cpu)
    elif val <= states[0] and val >= 400000:
        if update:
            update_pstate_freq(val, 2)
        write_freq(states[0], cpu)
    elif val >= states[1] and val <= max_freq:
        # Overclocking
        if update:
            update_pstate_freq(val, 0)
        write_freq(states[-1], cpu)
    return

def set_to_max_freq(cpu=None):
    """ Set all the cpus to max frequency"""
    max_freq = get_freq_bounds_ryzen()[1]
    if cpu is None:
        for c in range(psutil.cpu_count()):
            update_write_freq(max_freq, c)
    else:
        write_freq(max_freq, cpu)
    return max_freq

def set_to_freq(freq, cpu=None):
    """ Set all the cpus to max frequency"""
    if cpu is None:
        for c in range(psutil.cpu_count()):
            update_write_freq(freq, c)
    else:
        write_freq(freq, cpu)
    return freq

def set_seq_freqs(freq_seq, num_cores):
    """ Set all the cpus to sequentially reducing frequencies
        For Ryzen we only have three P-states """
    if num_cores > psutil.cpu_count(logical=False):
        # limit to max number of cores
        num_cores = psutil.cpu_count(logical=False)
    for c in range(num_cores):
        curr_freq = freq_seq[c%len(freq_seq)]
        write_freq(curr_freq, c*2)
        write_freq(curr_freq, c*2+1)
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
    #return (0.0211*(freq**2) - 0.4697*freq + 7.7535)*1000
    return round((0.231)*freq - 0.85, 4)*1000

def freq_at_power(power):
    #return int(-0.0773*((power/1000)**2)+ 3.7436*(power/1000) - 4.6404)*100000
    return quantize((((power/1000)+0.85)*13/3)*100000)

def change_freq(target_power, cpu=0, increase=False, Update=True):
    """ Update frequency based on target power and power model """
    # power differential to freq reduction factor
    new_freq = freq_at_power(target_power)
    old_freq = int(read_freq())
    # print(new_freq, old_freq, target_power)

    if abs(old_freq - new_freq) <= 25000:
        return old_freq

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
    # if new_freq < bounds[0]:
    #     new_freq = bounds[0]
    print("change_freq:", new_freq, old_freq, new_power, target_power)

    if new_freq < 400000:
        new_freq = 400000
    if new_freq > 3400000:
        new_freq = 3400000

    print("change_freq:", new_freq, old_freq, new_power, target_power)
    # WARN: Hardecoded cpu numbers below
    # update_write_freq(new_freq, cpu, update=Update)
    # if (cpu % 2) == 0:
    #     update_write_freq(new_freq, cpu+1, update=Update)
    # else:
    #     update_write_freq(new_freq, cpu-1, update=Update)
    return new_freq

def change_freq_std(target_pwr, current_pwr, old_freq=None, cpu=0, increase=False, Update=True):
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
    step = 25000

    # Select the right step size
    if power_diff < 300:
        # to close better settle than oscillate
        return new_freq
    elif power_diff > 1500 and power_diff < 3000:
        step = 100000
    elif power_diff > 3000 and power_diff < 7000:
        step = 200000
    elif power_diff > 7000:
        step = 500000

    if increase:
        new_freq = new_freq + step
    else:
        new_freq = new_freq - step

    bounds = get_freq_bounds_ryzen()

    # if new_freq < bounds[0]:
    #     new_freq = bounds[0]
    if new_freq < 800000:
        new_freq = 800000
    if new_freq > bounds[1]:
        new_freq = bounds[1]

    print("ch_freq_std ", cpu, target_pwr, new_freq, increase, power_diff, Update)
    # WARN: Hardecoded cpu numbers below
    #write_freq(new_freq, cpu)
    # update_write_freq(new_freq, cpu, update=Update)
    # if (cpu % 2) == 0:
    #     update_write_freq(new_freq, cpu+1, update=Update)
    # else:
    #     update_write_freq(new_freq, cpu-1, update=Update)

    return new_freq

def get_new_freq(target_pwr, current_pwr, old_freq, increase=False):
    """ Update frequency based on target power and actulal power value per core"""

    bounds = get_freq_bounds_ryzen()
    new_freq = old_freq
    power_diff = abs(current_pwr - target_pwr)
    step = 25000
    direction = math.copysign(1, (target_pwr - current_pwr))
   # Select the right step size
    if power_diff < 100:
        # to close better settle than oscillate
        return new_freq
    elif power_diff > 1000 and power_diff < 4000:
        step = 100000
    elif power_diff > 4000 and power_diff < 7000:
        step = 200000
    elif power_diff > 7000:
        step = 1000000

    new_freq = old_freq + direction*step
    if new_freq >= bounds[1]-25000:
        # at max value
        new_freq = bounds[1]
    elif new_freq <= bounds[0]+25000:
        # at lowest
        new_freq = bounds[0]

    print("new_freq_calculator ", target_pwr, new_freq, increase, power_diff, step, direction)
    return new_freq

def keep_limit(curr_power, limit, cpu=0, last_freq=None, first_limit=True, leader=False):
    """ Follow the power limit """
    new_limit = limit
    old_freq = last_freq

    if not first_limit:
#        if curr_power - limit > 0 and new_limit > 1000:
#            new_limit = new_limit - abs(curr_power - new_limit)/2
#            #new_limit = new_limit - 1000
#        elif curr_power - limit < 0 and new_limit > 1000:
#            new_limit = new_limit + abs(curr_power - new_limit)/4
#            #new_limit = new_limit + 1000
#
#    # print("In keep_limit ", limit)
        tolerance = 100
        if curr_power - limit > tolerance:
            # reduce frequency
            old_freq = change_freq_std(new_limit, curr_power, last_freq, cpu, Update=leader)
        elif limit - curr_power > tolerance:
            # print("Increase")
            old_freq = change_freq_std(new_limit, curr_power, last_freq, cpu, increase=True, Update=leader)
    else:
        # First Step
        if curr_power > limit:
            # reduce frequency
            old_freq = change_freq(new_limit, cpu, Update=leader)
        elif curr_power < limit:
            # print("Increase")
            old_freq = change_freq(new_limit, cpu, increase=True, Update=leader)
    return old_freq

def set_per_core_freq_old(freq_list, cores):
    """ Write Quantized Frequency Limits for given lists """
    print("updating cores: ", cores, [quantize(f) for f in freq_list])
    for i, core in enumerate(cores):
        # print(i, core, quantize(freq_list[i]))
        update_write_freq(quantize(freq_list[i]), core, update=True)
        if core % 2 == 0:
            write_freq(quantize(freq_list[i]), core+1)
        else:
            write_freq(quantize(freq_list[i]), core-1)
    return

def set_per_core_freq(freq_list, cores, leaders=None):
    """ Write Quantized Frequency Limits for given lists """
    bounds = get_freq_bounds()
    freqs = [quantize(f) for f in freq_list]
    freqs_set = set()
    if leaders != None:
        # hard coding leader core concept
        freqs_set = set([freqs[i] for i in leaders])
    else:
        freqs_set = set(freqs) # unique frequencies
    freq_dict = {0:set(), 1:set(), 2:set()} # what states need to be modified
    count_dict = {0:0, 1:0, 2:0} # How many options do we have
    need_sep = [False, False, False] # do we have any options at all
    
    # find seperate pstates
    for val in freqs_set:
        if val <= bounds[0]:
            count_dict[2] += 1
            freq_dict[2].add(min(val,bounds[0]))
            if count_dict[2] > 1:
                need_sep[2] = True
        elif val > bounds[0] and  val <= 3000000:
            count_dict[1] +=1
            freq_dict[1].add(min(val,3000000))
            if count_dict[1] > 1:
                need_sep[1] = True
        elif val > 3000000 and val <= bounds[1]:
            count_dict[0] +=1
            freq_dict[0].add(min(val,bounds[1]))
            if count_dict[0] > 1:
                need_sep[0] = True
    print(need_sep)
    print(count_dict)
    print(freq_dict)
    for key, value in freq_dict.items():
        freq_dict[key] = set(value)
    print(freq_dict)
    
    # decorator adapted from https://stackoverflow.com/questions/6254871/python-minnone-x
    skipNone = lambda fn : lambda *args : fn(val for val in args if val is not None)    
    
    # initialize bounds with 
    new_bounds = get_pstate_freqs()
    up_freq = [None,None,None]
    
    # Select three P_states
    if need_sep[2]:
        up_freq[2] = min(freq_dict[2])
        up_freq[1] = max(freq_dict[2])
        new_bounds = [skipNone(min)(up_freq[2], new_bounds[0]), skipNone(max)(up_freq[1],new_bounds[1]), skipNone(max)(up_freq[0],new_bounds[2])]
    elif freq_dict[2] != set():
        new_bounds[0] = freq_dict[2].pop()
    
    if need_sep[1]:
        up_freq[2] = min(freq_dict[1])
        up_freq[1] = max(freq_dict[1])
        new_bounds = [skipNone(min)(up_freq[2], new_bounds[0]), skipNone(min)(up_freq[1], new_bounds[1]), skipNone(max)(up_freq[0],new_bounds[2])]
    elif freq_dict[1] != set():
        new_bounds[1] = freq_dict[1].pop()
    
    if need_sep[0]:
        up_freq[1] = min(freq_dict[0])
        up_freq[0] = max(freq_dict[0])
        new_bounds = [skipNone(min)(up_freq[2], new_bounds[0]), skipNone(max)(up_freq[1],new_bounds[1]), skipNone(max)(up_freq[0],new_bounds[2])] 
    elif freq_dict[0] != set():
        new_bounds[2] = freq_dict[0].pop()
    # Update the P-States as needed
    for state, freq in enumerate(new_bounds[::-1]):
        if need_sep[state]:
            update_pstate_freq(freq, state)
    
    # Finally write the appropriate freq values

    print(new_bounds)
    # print_pstate_values()
    for i, core in enumerate(cores):
        ryzen_write_freq(freqs[i], new_bounds, cpu=core)
        if core % 2 == 0:
            ryzen_write_freq(freqs[i], new_bounds, cpu=core+1)
        else:
            ryzen_write_freq(freqs[i], new_bounds, cpu=core-1)

    return

def keep_limit_prop_freq(curr_power, limit, hi_freqs, low_freqs, hi_shares, low_shares, high_cores, low_cores, first_limit=False, lp_active=False):
    """ Proportional frequency power controller adapted from skylake branch """
    tolerance = 500
    max_per_core = max(hi_freqs)
    max_freq = 3400000
    alpha = abs(limit-curr_power)/TDP

    # print(limit)

    if abs(curr_power - limit) < tolerance:
        # at power limit nothing todo
        return False, hi_freqs, low_freqs
    elif (limit - curr_power) > -1*tolerance:
        # Below limit
        # We have excess power
        extra_freq = alpha * max_per_core
        ## distribute excess power - frequency among
        # First Check if high power apps are at max freq
        if not (hi_shares is None):
            shares_per_core = [hi_shares[i] if not (math.isclose(hi_freqs[i],3400000,rel_tol=0.001)) else 0 for i in range(len(high_cores))]
            sum_shares = sum(shares_per_core)
            if not math.isclose(sum_shares, 0):
                add_hi = [(s * extra_freq / sum_shares) for s in shares_per_core]
                extra_freq = extra_freq - sum(add_hi)
                hi_freqs = [ min(x+y, max_freq) for x,y in zip(add_hi, hi_freqs)]
                set_per_core_freq(hi_freqs, high_cores)
                max_per_core = max(hi_freqs)
        if not first_limit:
            if extra_freq > 200000 and lp_active:
                if not (low_shares is None):
                    add_lo = [s * extra_freq for s in low_shares]
                    extra_freq = extra_freq - sum(add_lo)
                    low_freqs = [ min(x+y, max_per_core) for x,y in zip(add_lo, low_freqs)]
                    set_per_core_freq(low_freqs, low_cores)
                return True, hi_freqs, low_freqs
            return False, hi_freqs, low_freqs
    elif (curr_power - limit) > tolerance:
        # Above limit
        # We have no excess power
        # remove extra frequency from low power first
        extra_freq = alpha * max_per_core
        if lp_active and not(low_shares is None):
            rem_lo = [s * extra_freq for s in low_shares]
            extra_freq = extra_freq - sum(rem_lo)
            low_freqs = [ y-x for x,y in zip(rem_lo, low_freqs)]
            set_per_core_freq(low_freqs, low_cores)

        # remove remaining frequency from hi power
        if not (hi_shares is None):
            shares_per_core = [hi_shares[i] if not (math.isclose(hi_freqs[i],800000,rel_tol=0.05)) else 0 for i in range(len(high_cores))]
            sum_shares = sum(shares_per_core)
            if not math.isclose(sum_shares, 0):
                rem_hi = [(s * extra_freq)/sum_shares for s in shares_per_core]
                extra_freq = extra_freq - sum(rem_hi)
                hi_freqs = [ y-x for x,y in zip(rem_hi, hi_freqs)]
                set_per_core_freq(hi_freqs, high_cores)

    return False, hi_freqs, low_freqs


def keep_limit_prop_power(curr_power, limit, hi_lims, low_lims, hi_freqs, low_freqs,
                          hi_shares, low_shares, high_cores, low_cores, hi_power, low_power,
                          first_limit=False, lp_active=False, hi_lead=None, low_lead=None):
    """ Proportional Core Power  Power controller adapted from skylake branch
        limit is package power limit; hi_lims and low_lims are per core limits
        TODO: Extend the shares mechanism to low power apps"""
    tolerance = 250
    max_power = 10000
    max_per_core = max(max(hi_lims), max(hi_power), max_power)
    # max_freq = 3400000
    alpha = abs(limit-curr_power)/TDP

    # print(limit, curr_power)

    if abs(curr_power - limit) < tolerance:
        # at power limit nothing todo
        return False, hi_lims, low_lims, hi_freqs, low_freqs
    elif (limit - curr_power) > -1*tolerance:
        # Below limit
        # We have excess power
        extra_power = alpha * max_per_core
        ## distribute excess power - frequency among
        # First Check if high power apps are at max freq
        if not (hi_shares is None):
            shares_per_core = [hi_shares[i] if not (math.isclose(3400, hi_freqs[i]/1000, abs_tol=25)) else 0 for i in range(len(high_cores))]
            sum_shares = sum(shares_per_core)
            print("Below Limit", sum_shares)
            if not math.isclose(sum_shares, 0):
                add_hi = [(s * extra_power / sum_shares) for s in shares_per_core]
                extra_power = extra_power - sum(add_hi)
                hi_lims = [min(x+y, max_per_core) for x,y in zip(add_hi, hi_lims)]
                if first_limit:
                    hi_freqs = [freq_at_power(l) for l in hi_lims]
                else:
                    hi_freqs = [get_new_freq(l,a,f,increase=True) for l,a,f in zip(hi_lims, hi_power, hi_freqs)]
                set_per_core_freq(hi_freqs, high_cores, leaders=hi_lead)
                # max_per_core = min(max(hi_lims), max(hi_power))
                # detect saturation 
                # hi_lims = [y if (math.isclose(3400, f/1000, abs_tol=25)) or (math.isclose(f/1000,800,abs_tol=25))  else x for x,y,f in zip(hi_lims, hi_power, hi_freqs)]
                # hi_lims = [y if (math.isclose(3400, f/1000, abs_tol=25)) else x for x,y,f in zip(hi_lims, hi_power, hi_freqs)]
        if not first_limit:
            if extra_power > 2000 and lp_active:
                if not (low_shares is None):
                    add_lo = [s * extra_power for s in low_shares]
                    extra_power = extra_power - sum(add_lo)
                    low_lims = [ min(x+y, max_per_core) for x,y in zip(add_lo, low_lims)]
                    low_freqs = [freq_at_power(l) for l in low_lims]
                    set_per_core_freq(low_freqs, low_cores, leaders=low_lead)
                return True, hi_lims, low_lims, hi_freqs, low_freqs
            return False, hi_lims, low_lims, hi_freqs, low_freqs
    elif (curr_power - limit) > tolerance:
        # Above limit
        # We have no excess power
        # remove extra frequency from low power first
        print("Above Limit")
        extra_power = alpha * max_per_core

        if lp_active and not(low_shares is None):
            rem_lo = [s * extra_power for s in low_shares]
            extra_power = extra_power - sum(rem_lo)
            low_lims = [ y-x for x,y in zip(rem_lo, low_lims)]
            low_freqs = [freq_at_power(l) for l in low_lims]
            set_per_core_freq(low_freqs, low_cores, leaders=low_lead)

        # remove remaining frequency from hi power
        if not (hi_shares is None):
            shares_per_core = [hi_shares[i] if not (math.isclose(hi_freqs[i]/1000,800, abs_tol=25)) else 0 for i in range(len(high_cores))]
            sum_shares = sum(shares_per_core)
            if not math.isclose(sum_shares, 0):
                rem_hi = [(s * extra_power)/sum_shares for s in shares_per_core]
                extra_power = extra_power - sum(rem_hi)
                hi_lims = [ y-x for x,y in zip(rem_hi, hi_lims)]
                if first_limit:
                    hi_freqs = [freq_at_power(l) for l in hi_lims]
                else:
                    hi_freqs = [get_new_freq(l,a,f,increase=False) for l,a,f in zip(hi_lims, hi_power, hi_freqs)]
                set_per_core_freq(hi_freqs, high_cores, leaders=hi_lead)
                # detect saturation
                hi_lims = [ y if (math.isclose(3400, f/1000,abs_tol=25)) else x for x,y,f in zip(hi_lims, hi_power, hi_freqs)]
    print(hi_freqs)
    return False, hi_lims, low_lims, hi_freqs, low_freqs
