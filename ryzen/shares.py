
from operator import itemgetter
from functools import reduce
from launcher import parse_file
from frequency import get_freq_bounds

TDP = 85000
# def get_freq_bounds():
#     """ Dummy for offline testing"""
#     return [800000, 3000000]

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

def allocate_shares_loop(limit, _proc, max_per_core, cores):
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

    print("FIRST ALLOCATION", cores_to_include, limit_per_core)
    count = 0

    # Check for leftover power
    left_over_pwr = left_over_pwr - sum(limit_per_core)

    while int(round(left_over_pwr, 0)) > 0:
        # we have left over power

        if int(round(left_over_pwr, 0) == 0):
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

    if len(high) == 0:
        # we got no High Powe applications
        high_set = None
        extra_pwr = limit
    else:
        extra_pwr, hi_limits, shares_high = allocate_shares_loop(limit, high, max_per_core, cores)
        print("Power left = ", extra_pwr)
        high_set = (hi_limits, shares_high, high)

    if int(round(extra_pwr, 0)) > 0:
        # We have power for low priority
        # First check if we have cores avialable
        cores_avil = cores-len(high)
        extra_pwr, lo_limits, shares_lo = allocate_shares_loop(extra_pwr, low, max_per_core, cores_avil)
        low_set = (lo_limits, shares_lo, low)

    return extra_pwr, high_set, low_set

def first_freq_allocation(power_limit, cores, app_file):
    list_procs = parse_file(app_file)
    list_procs.sort(key=itemgetter(3))
    
    high = [r for r in list_procs if r[3] < 0]
    low = [r for r in list_procs if r[3] > 0]

    #TDP = 85*1000
    alpha = 1
    if power_limit*1000 < TDP:
        alpha = power_limit*1000/float(TDP)
    # WARN: hard-coding max frequency for 10 active cores
    # add code to read directly from relevant MSR's
    # if len(list_procs) > 10:
    max_turbo = 2200000
    num_apps = min(len(list_procs),cores)
    if num_apps >= 10 and num_apps < 28:
        max_turbo = 2500000
    elif num_apps < 10 and num_apps > 4:
        max_turbo = 2700000
    elif num_apps <= 4 and num_apps > 2:
        max_turbo = 2800000
    elif len(list_procs) < 4:
        max_turbo = 3000000
    
    max_per_core = min(get_freq_bounds()[1],max_turbo)
    freq_limit = alpha * max_per_core * cores

    high_set = None
    low_set = None
    extra_freq = freq_limit
    
    print(freq_limit, alpha, max_per_core, max_turbo)

    if high is None:
        # we got no High Powe applications
        high_set = None
        extra_freq = freq_limit
    else:
        high.sort(key=itemgetter(2))
        extra_freq, hi_limits, shares_high = allocate_shares_loop(extra_freq, high, max_per_core, min(cores, len(high)))
        print("freq left = ", extra_freq)
        high_set = (hi_limits, shares_high, high)
    
    # First check if we have cores avialable
    cores_avil = cores if high is None else cores-len(high)
    
    # if int(round(extra_pwr, 0)) > 0 and not(low is None) and cores_avil > 0:
    if  not(low is None) and cores_avil > 0:
        # We have power for low priority
        low.sort(key=itemgetter(2)) 
        if int(round(extra_freq, 0)) > 0 :  
            extra_freq, lo_limits, shares_lo = allocate_shares_loop(extra_freq, low, max_per_core, cores_avil)
        else:
            # get case for 800 MHz per avialable core
            _,lo_limits, shares_lo = allocate_shares_loop(800000*cores_avil, low, max_per_core, cores_avil)
            extra_freq = None 
        low_set = (lo_limits, shares_lo, low)

    return extra_freq, high_set, low_set

def get_list_limits(power, cores, app_file):
    """ Get Priority Applications, and their corresponding Power Shares and Limits"""
    extra_power, high_set, low_set = first_allocation(power, cores, app_file)
    all_limits = None
    all_apps = None

    if not high_set is None:
        #We have high_prio apps
        all_limits = high_set[0]
        all_apps = high_set[2]

    if not low_set is None:
        #We have low_prio apps
        all_limits += low_set[0]
        all_apps += low_set[2]

    return all_apps, all_limits

def get_list_limits_cores(power, cores, app_file, opt="Freq"):
    high_set = None
    low_set = None
    all_limits = None
    high_apps = None
    low_apps = None
    high_cores = None
    low_cores = None
    high_limits = None
    low_limits = None
    high_shares = None
    low_shares = None
    start = 0
    end = 0
    
    if opt == "Freq":
        __, high_set, low_set = first_freq_allocation(power, cores, app_file)
    elif opt == "Power":
        __, high_set, low_set = first_allocation(power, cores, app_file)

    if not high_set is None:
        #We have high_prio apps
        all_limits = high_set[0]
        high_limits = high_set[0]
        high_shares = high_set[1]
        high_apps = high_set[2]
        high_cores = [i*2 for i in range(start, len(all_limits))]
        start = len(all_limits)
        end = 1

    if not low_set is None:
        #We have low_prio apps
        all_limits += low_set[0]
        low_limits = low_set[0]
        low_shares = low_set[1]
        low_apps = low_set[2]
        low_cores = [i*2 for i in range(start, start+min(len(low_set[0]), cores)+end)]

    return high_apps, high_cores, low_apps, low_cores, all_limits, high_limits, low_limits, high_shares, low_shares

def get_lists(power, cores, app_file):
    """ get high and low priority cores """
    list_procs = parse_file(app_file)
    list_procs.sort(key=itemgetter(3))
    high = [r for r in list_procs if r[3] < 0]
    low = [r for r in list_procs if r[3] > 0]
    high_cores = []
    low_cores = []
    if not (high is None):
        if len(high) >= cores:
            high_cores = range(cores)
            low = None
        elif len(high) >= 1:
            high_cores = range(0,len(high))
            if not (low is None):
                low_cores = range(len(high_cores), len(high_cores)+ 1 + min(cores - len(high_cores), len(low)))
    else:
        if not (low is None):
            low_cores = range(0, min(cores, len(low)))

    return high, high_cores, low, low_cores

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
