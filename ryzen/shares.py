from launcher import *
from tracker import *
from operator import itemgetter

list_procs = parse_file("input3")

limit = 30

max_per_core = 10000
cores = 4

# Sort the list according to priority
list_procs.sort(key=itemgetter(3))

left_over_pwr = 0

high = [r for r in list_procs if r[3] < 0]

def calc_share_ratios(list_prio, cores):
    # Shares calculation logic
    max_shares_per_app = 100
    # collect all high priority apps
    shares_per_app = None
    if len(list_prio) <= cores:
        total_shares = sum([r[2] for r in list_prio])
        shares_per_app = [r[2]/total_shares for r in list_prio]
    elif len(high) > cores:
        # we have more apps to run than core
        # Option 1 assume all High priority apps have the same shares
        #          Hence all of them will run under the same limit and
        #          linux scheduler can take care of them
        shares_per_app = [max_shares_per_app/(max_shares_per_app*cores)]*cores
        # we need to exit this function

        # Option 2 if we have shares, then collect all the different types of shares
        # if the types are less than equal to cores find proportional share  for
        # each core and pin the respective apps
    print(total_shares, shares_per_app)
    # we are done we can return shares_per_app
    return shares_per_app

shares_per_app = calc_share_ratios(high, cores)

limit_per_core = [r*limit*1000 if r*limit*1000 < max_per_core else max_per_core for r in shares_per_app]

if sum(limit_per_core) < limit:
    # we have left over power
    left_over_pwr = limit - sum(limit_per_core)
    # redistribute this power among the apps that didn't recieve it in the last
    # round of proportional share calculations
        # find apps and shares to consider
    a


shares_per_watt = [x[2]/y for x,y in zip(high, limit_per_core)]
