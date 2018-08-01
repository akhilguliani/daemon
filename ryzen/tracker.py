
class PerCoreTracker(dict):
    """
    Class for tracking percore energy values
    """
    def __add__(self, other):
        rv = PerCoreTracker()
        for key, value in self.items():
            if key in other.keys():
                rv[key] = value + other[key]
        return rv

    def __sub__(self, other):
        rv = PerCoreTracker()
        for key, value in self.items():
            if key in other.keys():
                rv[key] = value - other[key]
        return rv

    def __mul__(self, other):
        rv = PerCoreTracker()
        for key, value in self.items():
            if key in other.keys():
                rv[key] = value * other[key]
        return rv

    def __floordiv__(self, other):
        rv = PerCoreTracker()
        for key, value in self.items():
            if key in other.keys():
                rv[key] = value // other[key]
        return rv

    def __truediv__(self, other):
        rv = PerCoreTracker()
        for key, value in self.items():
            if key in other.keys():
                rv[key] = value / other[key]
        return rv

    def __div__(self, other):
        rv = PerCoreTracker()
        for key, value in self.items():
            if key in other.keys():
                rv[key] = value / other[key]
        return rv

    def __lt__(self, other):
        rv = PerCoreTracker()
        ret = True
        for key, value in self.items():
            if key in other.keys():
                rv[key] = value < other[key]
                ret = rv[key] or ret
        return ret, rv

    def __le__(self, other):
        rv = PerCoreTracker()
        ret = True
        for key, value in self.items():
            if key in other.keys():
                rv[key] = value <= other[key]
                ret = rv[key] or ret
        return ret, rv

    def __eq__(self, other):
        rv = PerCoreTracker()
        ret = True
        for key, value in self.items():
            if key in other.keys():
                rv[key] = value == other[key]
                ret = rv[key] or ret
        return ret, rv

    def __int__(self, ndigits):
        for key, value in self.items():
            self[key] = int(value)
        return self

    def __round__(self, ndigits):
        for key, value in self.items():
            self[key] = round(value, ndigits)
        return self

    def __abs__(self):
        for key, value in self.items():
            self[key] = abs(value)
        return self

    def scalar_div(self, val):
        rv = PerCoreTracker()
        ret = True
        for key, value in self.items():
            rv[key] = value / val
        return rv

    def scalar_mul(self, val):
        for key, value in self.items():
            self[key] = value * val
        return self

def update_delta_32(before, after):
    """ Takes two PerCoreTracker Dicts and returns update delta """
    if (before is None) or (after is None):
        return 0
    lesser = (after < before)
    if  lesser[0]:
        # One of the values has over-flowed
        ret = PerCoreTracker()

        for key, value in lesser[1].items():
            if value:
                ret[key] = 0x100000000 + after[key]
            else:
                ret[key] = after[key] - before[key]

        return ret
    else:
        # no overflow return difference
        return after - before

def update_delta(before, after):
    """ Takes two PerCoreTracker Dicts and returns update delta """
    if (before is None) or (after is None):
        return 0
    lesser = (after < before)
    if  lesser[0]:
        # One of the values has over-flowed
        ret = PerCoreTracker()

        for key, value in lesser[1].items():
            if value:
                ret[key] = after[key]
            else:
                ret[key] = after[key] - before[key]

        return ret
    else:
        # no overflow return difference
        return after - before

