
from operator import itemgetter
from functools import reduce
from launcher import parse_file
from frequency import get_freq_bounds_ryzen

def calc_share_ratios(list_prio, cores):
    """ Basic Shares calculator"""
    # Shares calculation logic
    max_shares_per_app = 100
    # collect all high priority apps
    shares_per_app = None
    if len(list_prio) <= cores:
        total_shares = sum([r[2] for r in list_prio])
        shares_per_app = [r[2]/total_shares for r in list_prio]
        print(total_shares, shares_per_app)

    elif len(list_prio) > cores:
        # we have more apps to run than core
        # Option 1 assume all High priority apps have the same shares
        #          Hence all of them will run under the same limit and
        #          linux scheduler can take care of them
        shares_per_app = [max_shares_per_app/(max_shares_per_app*cores)]*cores
    # we are done we can return shares_per_app
    return shares_per_app

def calc_share_ratios_2(list_prio, inc_cores, ratios):
    sum_shares = 0
    for i, work in enumerate(list_prio):
        if inc_cores[i]:
            sum_shares += work[2]
    shares = [r[2]/sum_shares if inc_cores[i] else ratios[i] for i, r in enumerate(list_prio)]

    print("r2", sum_shares, shares)

    return shares

def allocate_shares_loop(limit, _proc, max_per_core, cores, spill):
    shares_app = calc_share_ratios(_proc, cores)
    left_over_pwr = limit
    limit_per_core = None

    # allocate
    if limit > min(len(_proc),cores)*max_per_core:
        # Have more power than needs allocation
        limit_per_core = [max_per_core]*min(len(_proc), cores)
        left_over_pwr = left_over_pwr - min(len(_proc), cores)*max_per_core
        return left_over_pwr, limit_per_core, shares_app

    # Allocate and check
    limit_per_core = [min(r*limit, max_per_core) for r in shares_app]
    cores_to_include = [False if r >= max_per_core else True for r in limit_per_core]

    count = 0

    # Check for leftover power
    left_over_pwr = left_over_pwr - sum(limit_per_core)

    print("FIRST ALLOCATION", cores_to_include, limit_per_core, left_over_pwr)

    while int(round(left_over_pwr, 0)) > spill:
        # we have left over power

        if int(round(left_over_pwr, 0) <= spill):
            print("END")
            break

        if reduce((lambda x, y: x and y), cores_to_include):
            left_over_pwr = left_over_pwr - sum(limit_per_core)
            break

        # redistribute this power among the apps that didn't recieve it in the last
        # round of proportional share calculations
        #   find apps and shares to consider
        ncores = len([x for x in cores_to_include if x])
        if ncores == 1:
            limit_per_core = [min(l+(1*left_over_pwr), max_per_core) if c else l for l, c in zip(limit_per_core, cores_to_include)]
            left_over_pwr = left_over_pwr - sum(limit_per_core)
            break
        elif ncores < 1:
            # Excess power
            break
        else:
            shares_app = calc_share_ratios_2(_proc, shares_app, cores_to_include)
            limit_per_core = [min(l+(r*left_over_pwr), max_per_core) if c else l for l, r, c in zip(limit_per_core, shares_app, cores_to_include)]
            print(str(count), left_over_pwr, limit_per_core, shares_app)
        count += 1

        cores_to_include = [False if r >= max_per_core else True for r in limit_per_core]
        left_over_pwr = left_over_pwr - sum(limit_per_core)
    print("Entity left = ", left_over_pwr)
    left_over_pwr = 0 if left_over_pwr < 0 else left_over_pwr
    return left_over_pwr, limit_per_core, shares_app


def first_allocation(power, cores, app_file):
    list_procs = parse_file(app_file)
    list_procs.sort(key=itemgetter(3))

    limit = power*1000
    max_per_core = 10000
    # cores = 4
    high = [r for r in list_procs if r[3] < 0]
    low = [r for r in list_procs if r[3] > 0]

    high_set = None
    low_set = None

    if high is None:
        # we got no High Powe applications
        high_set = None
        extra_pwr = limit
    else:
        high.sort(key=itemgetter(2))
        extra_pwr, hi_limits, shares_high = allocate_shares_loop(limit, high, max_per_core, cores, 0)
        print("Power left = ", extra_pwr)
        high_set = (hi_limits, shares_high, high)

    cores_avil = cores if high is None else cores-len(high)
    # if int(round(extra_pwr, 0)) > 0 and not(low is None) and cores_avil > 0:
    if  not(low is None) and cores_avil > 0:
        # We have power for low priority
        # First check if we have cores avialable
        low.sort(key=itemgetter(2)) 
        if int(round(extra_pwr, 0)) > 0 :  
            extra_pwr, lo_limits, shares_lo = allocate_shares_loop(extra_pwr, low, max_per_core, cores_avil, 0)
        else:
            # get case for 1 W per avialable core
            _,lo_limits, shares_lo = allocate_shares_loop(1000*cores_avil, low, max_per_core, cores_avil, 0)
            extra_pwr = None 
        low_set = (lo_limits, shares_lo, low)

    return extra_pwr, high_set, low_set

def get_list_limits(power, cores, app_file):
    extra_power, high_set, low_set = first_allocation(power, cores, app_file)
    all_limits = None
    all_apps = None

    if not high_set is None:
        #We have high_prio apps
        all_limits = high_set[0]
        all_apps = high_set[2]

    if not low_set is None:
        #We have low_prio apps
        if not(extra_power is None):
            all_limits += low_set[0]
        all_apps += low_set[2]

    return all_apps, all_limits

def first_freq_allocation(power_limit, cores, app_file):
    list_procs = parse_file(app_file)
    list_procs.sort(key=itemgetter(3))
    bounds = get_freq_bounds_ryzen()
    
    high = [r for r in list_procs if r[3] < 0]
    low = [r for r in list_procs if r[3] > 0]

    TDP = 85*1000
    alpha = 1
    if power_limit*1000 < TDP:
        alpha = power_limit*1000/float(TDP)
    # WARN: hard-coding max frequency for 10 active cores
    # add code to read directly from relevant MSR's
    # if len(list_procs) > 10:
    max_turbo = 3400000
    
    max_per_core = min(get_freq_bounds_ryzen()[1],max_turbo)
    freq_limit = alpha * max_per_core * cores

    high_set = None
    low_set = None
    extra_freq = freq_limit
    
    print("FREQ CONFIG: ", power_limit, freq_limit, alpha, max_per_core, max_turbo)

    if high is None:
        # we got no High Powe applications
        high_set = None
        extra_freq = freq_limit
    else:
        high.sort(key=itemgetter(2))
        extra_freq, hi_limits, shares_high = allocate_shares_loop(extra_freq, high, max_per_core, min(cores, len(high)), 100000)
        # WARN: Hack for fixing lower limit for frequency
        hi_limits = [max(h, bounds[0]) for h in hi_limits] 
        print("freq left = ", extra_freq)
        high_set = (hi_limits, shares_high, high)
    
    # First check if we have cores avialable
    cores_avil = cores if high is None else cores-len(high)
    
    # if int(round(extra_pwr, 0)) > 0 and not(low is None) and cores_avil > 0:
    if  not(low is None) and cores_avil > 0:
        # We have power for low priority
        low.sort(key=itemgetter(2)) 
        if int(round(extra_freq, 0)) > 0 :  
            extra_freq, lo_limits, shares_lo = allocate_shares_loop(extra_freq, low, max_per_core, cores_avil, 100000)
        else:
            # get case for 800 MHz per avialable core
            _,lo_limits, shares_lo = allocate_shares_loop(800000*cores_avil, low, max_per_core, cores_avil, 100000)
            # WARN: Hack for fixing lower limit for frequency
            lo_limits = [max(l, bounds[0]) for l in lo_limits] 
            extra_freq = None 
        low_set = (lo_limits, shares_lo, low)

    return extra_freq, high_set, low_set

def first_perf_allocation(power_limit, cores, app_file):
    list_procs = parse_file(app_file)
    list_procs.sort(key=itemgetter(3))
    
    high = [r for r in list_procs if r[3] < 0]
    low = [r for r in list_procs if r[3] > 0]

    TDP = 85*1000
    alpha = 1
    if power_limit*1000 < TDP:
        alpha = (power_limit*1000)/float(TDP)
 
    max_per_core = 100
    perf_limit = alpha * max_per_core * cores

    high_set = None
    low_set = None
    extra_freq = perf_limit
    
    print("PERF CONFIG: ", power_limit*1000, perf_limit, alpha, max_per_core)

    if high is None:
        # we got no High Powe applications
        high_set = None
        extra_freq = perf_limit
    else:
        high.sort(key=itemgetter(2))
        extra_freq, hi_limits, shares_high = allocate_shares_loop(extra_freq, high, max_per_core, min(cores, len(high)), 1)
        # WARN: Hack for fixing lower limit for frequency
        # hi_limits = [max(h, 100) for h in hi_limits] 
        print("freq left = ", extra_freq)
        high_set = (hi_limits, shares_high, high)
    
    # First check if we have cores avialable
    cores_avil = cores if high is None else cores-len(high)
    
    # if int(round(extra_pwr, 0)) > 0 and not(low is None) and cores_avil > 0:
    if  not(low is None) and cores_avil > 0:
        # We have power for low priority
        low.sort(key=itemgetter(2)) 
        if int(round(extra_freq, 0)) > 0 :  
            extra_freq, lo_limits, shares_lo = allocate_shares_loop(extra_freq, low, max_per_core, cores_avil, 1)
        else:
            # get case for 800 MHz per avialable core
            _,lo_limits, shares_lo = allocate_shares_loop(1*cores_avil, low, max_per_core, cores_avil, 1)
            # WARN: Hack for fixing lower limit for frequency
            # lo_limits = [max(l, 1) for l in lo_limits] 
            extra_freq = None 
        low_set = (lo_limits, shares_lo, low)

    return extra_freq, high_set, low_set

def get_list_limits_cores(power, cores, app_file, opt="Power"):
    high_set = None
    low_set = None
    all_limits = None
    all_shares = None
    high_apps = None
    low_apps = None
    high_cores = None
    low_cores = None
    high_limits = None
    low_limits = None
    high_shares = None
    low_shares = None
    start = 0

    if opt == "Freq":
        __, high_set, low_set = first_freq_allocation(power, cores, app_file)
    elif opt == "Power":
        __, high_set, low_set = first_allocation(power, cores, app_file)
    elif opt == "Perf":
        __, high_set, low_set = first_perf_allocation(power, cores, app_file)

    if not high_set is None:
        #We have high_prio apps
        all_limits = high_set[0]
        high_limits = high_set[0]
        high_shares = high_set[1]
        high_apps = high_set[2]
        high_cores = [i*2 for i in range(start, len(all_limits))]
        all_shares = high_set[1] # get high shares 
        start = len(all_limits)

    if not low_set is None:
        #We have low_prio apps
        all_limits += low_set[0]
        low_limits = low_set[0]
        low_shares = low_set[1]
        low_apps = low_set[2]
        low_cores = [i*2 for i in range(start, min(start+len(low_set[0]), cores))]
        if not (low_cores is None):
            all_shares += [low_set[1][i] for i in range(len(low_cores))] # get high shares

    return high_apps, high_cores, low_apps, low_cores, all_limits, high_limits, low_limits, high_shares, low_shares, all_shares
    # return high_apps, high_cores, low_apps, low_cores, all_limits, all_shares

def get_new_limits(all_shares, start_index, excess_power, all_limits, cores, alpha=1, freqs=None):
    print("UPDATE LIMITS:", all_shares)
    import math
    excess_per_core = [0 for i in range(cores)]
    new_limits = all_limits
    if freqs is None:
        excess_per_core = [all_shares[i]*alpha*excess_power if i >= start_index else 0 for i in range(cores)]
        new_limits = [all_limits[i] + excess_per_core[i] for i in range(cores) ]
    else:
        # take freq into account
        excess = excess_power
        count = 0
        while not(math.isclose(excess,0,rel_tol=0.05)):
            excess_per_core = [all_shares[i] if not (math.isclose(freqs[i],3400000,rel_tol=0.05)) else 0 for i in range(cores)]
            total_shares = sum(excess_per_core)
            excess_per_core = [(E/total_shares)*alpha*excess for E in excess_per_core]
            new_limits = [new_limits[i] + excess_per_core[i] for i in range(cores)]
            excess = excess - sum(excess_per_core)
            count += 1
            if count == 100:
                break
        
    return new_limits

def test():
    for infile in ["inputs/input3", "inputs/i3070", "./inputs/input10050"]:
        for lim, cor in zip([25, 30, 35, 40],[4, 4, 4, 4]):
            a,b,c = first_allocation(lim, cor, infile)
            print(lim, cor)
            if c is None :
                print(a, b[0], "None")
            if b is None :
                print(a, "None", c[0])
            else:
                print(a, b[0], c[0])
            print("-------")
        print("________________")
