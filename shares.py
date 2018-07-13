from launcher import *
from tracker import *
from operator import itemgetter

list_procs = parse_file("input3")

limit = 30

max_per_core = 10

list_procs.sort(key=itemgetter(3))

high = [ r for r in list_procs if r[3] < 0]
total_shares = sum([r[2] for r in high])
shares_per_app = [r[2]/total_shares for r in high]

print(total_shares, shares_per_app)

limit_per_core = [r*limit*1000 if r*limit < 10 else 10*1000 for r in shares_per_app]

shares_per_watt = [x[2]/y for x,y in zip(high, limit_per_core)]
