from launcher import *
from tracker import *
from operator import itemgetter
from functools import reduce

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

def power_shares_loop(limit, _proc, max_per_core, cores):
    shares_app = calc_share_ratios(_proc, cores)
    left_over_pwr = limit
    limit_per_core = 0

    # allocate
    if limit > len(_proc)*max_per_core:
        # Have more power than needs allocation
        limit_per_core = [max_per_core]*len(_proc)
        left_over_pwr = limit - len(_proc)*max_per_core
        return left_over_pwr, limit_per_core

    # Allocate and check
    limit_per_core = [min(r*limit, max_per_core) for r in shares_app]
    cores_to_include = [False if r >= max_per_core else True for r in limit_per_core]

    print("FIRST ALLOCATION", cores_to_include, limit_per_core)
    count = 0

    while sum(limit_per_core) < limit:
        # we have left over power
        left_over_pwr = limit - sum(limit_per_core)

        if int(round(left_over_pwr, 0) == 0):
            print("ERROR")
            break
        if left_over_pwr < 0:
            # Should not happens
            print("ERROR")
            break

        # redistribute this power among the apps that didn't recieve it in the last
        # round of proportional share calculations
        #   find apps and shares to consider
        cores_to_include = [False if r >= max_per_core else True for r in limit_per_core]
        if reduce((lambda x, y: x and y), cores_to_include):
            break
        ncores = len([x for x in cores_to_include if x])
        if ncores == 1:
            limit_per_core = [min(l+(1*left_over_pwr), max_per_core) if c else l for l, c in zip(limit_per_core, cores_to_include)]
         ### Exit at this point
            break
        elif ncores < 1:
            # Excess power
            break
        else:
            ratios = calc_share_ratios_2(_proc, shares_app, cores_to_include)
            limit_per_core = [min(l+(r*left_over_pwr), max_per_core) if c else l for l, r, c in zip(limit_per_core, ratios, cores_to_include)]
            print(str(count), left_over_pwr, limit_per_core, ratios)
        count += 1

    left_over_pwr = limit - sum(limit_per_core)

    return left_over_pwr, limit_per_core


def test(power, cores):
    list_procs = parse_file("inputs/input3")
    list_procs.sort(key=itemgetter(3))

    limit = power*1000
    max_per_core = 10000
    # cores = 4
    high = [r for r in list_procs if r[3] < 0]
    low = [r for r in list_procs if r[3] > 0]

    left_over_pwr, _limits = power_shares_loop(limit, high, max_per_core, cores)
    if left_over_pwr > 0:
        # We have power for low priority
        # First check if we have cores avialable
        cores_avil = cores-len(high)
        low_power, low_limits = power_shares_loop(limit, high, max_per_core, cores_avil)
    else:
        return (left_over_pwr, _limits, high),(None, None, low)

test()
#        shares_per_watt = [x[2]/y for x,y in zip(_proc,  limit_per_core)]
